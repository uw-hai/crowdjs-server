from app import app
from flask.ext.security import login_required, current_user, auth_token_required
from schema.worker import Worker
from schema.answer import Answer
from schema.task import Task
from schema.requester import Requester
from schema.inferenceJob import InferenceJob
from redis_util import redis_get_worker_assignments_var, redis_get_task_queue_var
from aggregation import db_inference

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

def start_inference_job(job_id):
    # TODO put this in its own file, will need to do some background process management
    # TODO for now runs the entire inference job in this thread,
    # does NOT run in a background process right now - very bad!
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
        pomdp_controller = POMDPController(task_id)
        results = pomdp_controller.getStatus(task_id)
        #write result to DB
        job.results = results
        job.status = 'Completed'
        job.save()
    else:
        print "Error: don't know how to run the job=", job.to_json()
