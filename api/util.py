from app import app
from flask.ext.security import login_required, current_user, auth_token_required
from schema.question import Question
from schema.worker import Worker
from schema.answer import Answer
from schema.task import Task
from schema.requester import Requester
from schema.inferenceJob import InferenceJob
from redis_util import redis_get_worker_assignments_var, redis_get_task_queue_var
from aggregation import db_inference
from mongoengine.queryset import DoesNotExist
from redis.exceptions import WatchError
import datetime

from controllers.pomdp_controller import POMDPController

def requester_token_match(requester_id):
    return str(current_user.id) == requester_id

def requester_token_match_and_task_match(requester_id, task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return (str(current_user.id) == requester_id and
            str(task.requester.id) == requester_id)

def requester_task_match(requester_id, task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return str(task.requester.id) == requester_id

    
def get_or_insert_worker(worker_id, worker_source):
    if worker_source == 'mturk':
        try:
            worker = Worker.objects.get(platform_id = worker_id,
                                        platform_name = 'mturk')
        except:
            worker = Worker(platform_id = worker_id,
                            platform_name = 'mturk')
            worker.save()
        return worker
    else:
        return None

def get_alive_answers(question):
    answers = Answer.objects(question=question)
    answers = filter(lambda answer: answer.is_alive, answers)

    return answers

def clear_task_from_redis(task_id):
    
    num_questions_deleted = 0
    for assign_strategy in ['min_answers']:
        task_queue_var = redis_get_task_queue_var(task_id,
                                                  assign_strategy)
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        num_questions_deleted += len(task_queue)
        app.redis.delete(task_queue_var)


    worker_assignments_deleted = 0
    for worker in Worker.objects():
        worker_assignments_var = redis_get_worker_assignments_var(
            task_id, worker.id)
        worker_assignments_deleted += app.redis.delete(
            worker_assignments_var)
        

    return (num_questions_deleted, worker_assignments_deleted)

def get_requester_document(requester_id):
    """
    Find the requester's (should be current user's) requester document, if it exists.
    """
    try:
        requester_doc = Requester.objects.get(id = requester_id) #current_user
    except:
        return False
    return requester_doc

def get_task_document(task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return task

@app.celery.task(name='start_inference_job')
def start_inference_job(job_id):
    job = InferenceJob.objects.get(id = job_id)
    job.status = 'Running'
    job.save()

    task_id = job.task.id
    if job.strategy == "majority_vote":
        #run inference algorithm
        print "Running inference job with strategy =  majority_vote"
        results = db_inference.aggregate_task_majority_vote(task_id)
        #write result to DB
        job.results = results
        job.status = 'Completed'
        job.save()
    elif job.strategy == "EM":
        print "Running inference job with strategy =  EM"
        #run EM
        results = db_inference.aggregate_task_EM(task_id)
        #write result to DB
        job.results = results
        job.status = 'Completed'
        job.save()
    elif job.strategy == "pomdp":
        print "Running inference job with strategy =  pomdp"
        #get pomdp status for all questions in task
        pomdp_controller = POMDPController(task_id, settings = job.additional_params)
        results = pomdp_controller.getStatus(task_id)
        #write result to DB
        job.results = results
        job.status = 'Completed'
        job.save()
    else:
        print "Error: don't know how to run the job=", job.to_json()

@app.celery.task(name='requeue')
def requeue():
    question_ids_to_requeue = []
    worker_ids_to_requeue = []
    
    current_time = datetime.datetime.now()
    current_assignments = Answer.objects(
        status = 'Assigned')
    
    num_assignments = 0
    for assignment in current_assignments:
        assignment_duration = assignment.task.assignment_duration
        time_delta = current_time - assignment.assign_time
        num_assignments += 1
        print "Checking if time to requeue"
        print time_delta.total_seconds()
        print assignment_duration
        print current_time
        print assignment.assign_time
        
        if time_delta.total_seconds() > assignment_duration:
            requeueHelper(assignment.task.id, assignment.requester.id,
                          [assignment.question.id],
                          [assignment.worker.platform_id],
                          assignment.worker.platform_name,
                          'min_answers')

    print num_assignments
    return True

def requeueHelper(task_id, requester_id, question_ids,
                  worker_ids, worker_source,
                  strategy):
    
    num_question_ids = len(question_ids)

    print "Attempting to requeue questions"
    print question_ids
    
    for worker_id, question_id in zip(worker_ids, question_ids):
        try:
            question = Question.objects.get(
                id=question_id,
                task=task_id)
            worker = Worker.objects.get(
                platform_id = worker_id,
                platform_name = worker_source)
            if Answer.objects(task=task_id,
                              question = question,
                              worker = worker,
                              status = 'Assigned').first() == None:
                return {'error': 'Sorry, one of the question_id/worker_id pairsyou have provided is not eligible for requeueing'}
        except DoesNotExist:
            return {'error': 'Sorry, one of the question_id/worker_id pairsyou have provided is not eligible for requeueing'}





    task_questions_var = redis_get_task_queue_var(task_id, strategy)

    while 1:
        for (question_id, worker_id) in zip(question_ids, worker_ids):
            worker = Worker.objects.get(
                platform_id = worker_id,
                platform_name = worker_source)

            worker_assignments_var = redis_get_worker_assignments_var(
                task_id,
                worker.id)
            try:
                pipe = app.redis.pipeline()
                pipe.watch(task_questions_var)
                pipe.watch(worker_assignments_var)

                question = Question.objects.get(
                    id=question_id,
                    task=task_id)

                if pipe.zscore(task_questions_var, question_id) == None:
                    pipe.zadd(task_questions_var,
                              question.answers_per_question-1,
                              question_id)
                else:
                    pipe.zincrby(task_questions_var, question_id, -1)

                answer = Answer.objects(
                    task=task_id,
                    question = question_id,
                    worker = worker,
                    status = 'Assigned').delete()
                pipe.srem(worker_assignments_var, question_id)
            except WatchError:
                continue
            finally:
                pipe.reset()
        break
    print '%s questions requeued' % num_question_ids
    return {'success' : '%s questions requeued' % num_question_ids}
