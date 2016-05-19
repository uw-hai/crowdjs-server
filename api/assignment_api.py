from app import app
from redis_util import *
from flask.ext.restful import reqparse, abort, Api, Resource
import flask.ext.restful.inputs
from flask.ext.security import login_required, current_user, auth_token_required
from flask.ext.cors import cross_origin
import datetime
import schema.question
import schema.task
import schema.requester
import schema.answer
import json
import random
from util import requester_token_match, requester_token_match_and_task_match, get_or_insert_worker, get_alive_answers, requester_task_match
import sys, traceback

nextq_parser = reqparse.RequestParser()
#TODO:
#The worker id should not be required
nextq_parser.add_argument('worker_id', type=str, required=True)
nextq_parser.add_argument('worker_source', type=str, required=True)
nextq_parser.add_argument('task_id', type=str, required=True)
nextq_parser.add_argument('requester_id', type=str, required=True)
nextq_parser.add_argument('strategy', type=str, required=False,
                          default='random')
nextq_parser.add_argument('preview', type=flask.ext.restful.inputs.boolean,
                          required=False,
                          default=False)


class NextQuestionApi(Resource):
    """
    Usage:
    GET /url with JSON={worker_id:XXX, task_id:XXX [,strategy:XXX]}
    """
    #decorators = [cross_origin()]
    
    def get(self):

        """
        Assign a question from the given task to the given worker.
        """

        args = nextq_parser.parse_args()
            
        strategy = args['strategy']
        preview = args['preview']
        task_id = args['task_id']

        requester_id = args['requester_id']
        
        if not requester_task_match(requester_id, task_id):
            return "Sorry, your requester_id and task_id do not match"

        task = schema.task.Task.objects.get_or_404(id=task_id)
        requester = schema.requester.Requester.objects.get_or_404(
            id=requester_id)
        worker_platform_id = args['worker_id']
        worker_source = args['worker_source']

        sys.stdout.flush()
        worker = get_or_insert_worker(worker_platform_id, worker_source)
        if worker == None:
            return "You have not entered a valid worker source. It must be one of: [mturk,] "

        current_assignment = schema.answer.Answer.objects(
            task = task,
            worker=worker,
            status = 'Assigned')

        if len(current_assignment) == 1:
            return {'question_name' : current_assignment[0].question.name,
                    'question_id': str(current_assignment[0].question.id)}

        #If the task budget has been reached, then make no more assignemnts
        if (len(schema.answer.Answer.objects(task=task, is_alive=True)) >=
            task.total_task_budget and task.total_task_budget != -1):
            return {'error' : 'The total task budget has been reached'}
        
        if strategy == 'min_answers':
            question = self.min_answers(task_id, worker)
        elif strategy == 'random':
            question = self.random_choice(task_id, worker)
        else:
            return {'error' : 'Invalid Strategy'}

        if question == None:
            return {'error' : 'The strategy did not assign any question'}
        

        if not preview:
            answer = schema.answer.Answer(question = question,
                                          task = task,
                                      requester=requester,
                                          worker = worker,
                                          status = 'Assigned',
                                          assign_time=datetime.datetime.now,
                                          is_alive = True)
            
            answer.save()
            #REDIS update
            app.redis.sadd(redis_get_worker_assignments_var(task_id, worker.id), str(question.id))
            #min_answers: increment priority of the question that was assigned
            if strategy == 'min_answers':
                app.redis.zincrby(redis_get_task_queue_var(task_id, strategy),
                                  str(question.id),
                                  1)

                #If this assignemnt causes the question to
                #reach its allocated budget,
                #Remove it from the queue.
                #if the worker doesn't do the assignment, then the
                #question has to be replaced in the queue
                
                
                if app.redis.zscore(
                        redis_get_task_queue_var(task_id, 'min_answers'),
                        str(question.id)) >= question.answers_per_question:
                    app.redis.zrem(
                        redis_get_task_queue_var(task_id, 'min_answers'),
                        str(question.id))

        return {'question_name' : str(question.name),
                'question_id' : str(question.id)}

    ####
    # NOT FULLY TESTED
    ####
    def random_choice(self, task_id, worker):

        task = schema.task.Task.objects.get_or_404(id=task_id)

        questions = schema.question.Question.objects(task=task)
        
        qlist = list(questions)

        #First filter for questions that are alive
        filtered_qlist = filter(
            lambda q:len(get_alive_answers(q)) < q.answers_per_question,
            qlist)

        #Next filter out the questions that the worker has already
        #answered
        filtered_qlist = filter(
            lambda q:
            len(schema.answer.Answer.objects(question=q, worker=worker,
                                             status='Completed')) == 0,
            filtered_qlist)

        
        if len(filtered_qlist) == 0:
            return None
        question = random.choice(filtered_qlist)
        return question

    def min_answers(self, task_id, worker):
        """
        Assumes that task and worker IDs have been checked.
        """

        worker_id = worker.id
        chosen_question = None
        task = schema.task.Task.objects.get_or_404(id=task_id)

        task_questions_var = redis_get_task_queue_var(task_id, 'min_answers')
        worker_assignments_var = redis_get_worker_assignments_var(task_id, worker_id)

        #print "true task questions from DB with # of assignments+completed answers:"
        #for q in schema.question.Question.objects(task=task_id):
        #    print q.name, len(schema.answer.Answer.objects(question=q))
        
        #print "true worker assignments from DB (qname, value):"
        #for a in schema.answer.Answer.objects(worker=worker,task=task_id):
        #    print a.question.name, a.value
        task_questions = app.redis.zrange(task_questions_var, 0, -1)
        for question in task_questions:

            #Only assign a question if the worker has not been assigned it
            if not app.redis.sismember(worker_assignments_var, question):
                
                question_obj = schema.question.Question.objects.get(
                    id=question)

                if question_obj.answers_per_question:
                    if app.redis.zscore(task_questions_var, question) < question_obj.answers_per_question:
                        chosen_question = question
                        break
                else:
                    chosen_question = question

        redis_chosen_question=chosen_question

        if redis_chosen_question is None:
            return None
        else:
            return schema.question.Question.objects.get(
                id=redis_chosen_question)
