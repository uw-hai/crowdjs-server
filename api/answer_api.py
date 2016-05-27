from app import app
from redis_util import *
from flask.ext.restful import reqparse, abort, Api, Resource
import flask.ext.restful.inputs
from flask.ext.security import login_required, current_user, auth_token_required
from flask import url_for
from schema.answer import Answer
from schema.question import Question
from schema.worker import Worker
from schema.requester import Requester
from schema.task import Task
from util import get_or_insert_worker, requester_token_match_and_task_match, requester_token_match, requester_task_match
import datetime
import json
import sys, traceback
from redis.exceptions import WatchError


answer_parser = reqparse.RequestParser()
answer_parser.add_argument('requester_id', type=str, required=True)
answer_parser.add_argument('task_id', type=str, required=True)
answer_parser.add_argument('question_name', type=str, required=True)
answer_parser.add_argument('worker_id', type=str, required=True)
answer_parser.add_argument('worker_source', type=str, required=True)
answer_parser.add_argument('value', type=str, required=True)
answer_parser.add_argument('is_alive', type=flask.ext.restful.inputs.boolean,
                           required=False,
                           default=False)

answer_get_parser = reqparse.RequestParser()
answer_get_parser.add_argument('requester_id', type=str, required=True)
answer_get_parser.add_argument('task_id', type=str, required=False)
answer_get_parser.add_argument('completed', type=bool, required=False,
                               default = True)

class AnswerListApi(Resource):

    @auth_token_required
    def get(self):
        """
        Get list of all answers.
        """
        args = answer_get_parser.parse_args()
        requester_id = args['requester_id']
        task_id = args['task_id']
        completed = args['completed']

        if task_id == None:
            if not requester_token_match(requester_id):
                return "Sorry, your api token is not correct"
            requester = Requester.objects.get_or_404(id=requester_id)
            if completed:
                answers = Answer.objects(requester = requester,
                                         status='Completed')
            else:
                answers = Answer.objects(requester = requester)
                
        else:
            if not requester_token_match_and_task_match(requester_id, task_id):
                return "Sorry, your api token is not correct"

            requester = Requester.objects.get_or_404(id=requester_id)
            task = Task.objects.get_or_404(id=task_id)

            if completed:
                answers = Answer.objects(requester = requester, task = task,
                                         status='Completed')
            else:
                answers = Answer.objects(requester = requester, task = task)

                
            
        return json.loads(answers.to_json())

    def put(self):
        """
        Create a new answer.
        """
        args = answer_parser.parse_args()

        requester_id = args['requester_id']
        task_id = args['task_id']
        
        if not requester_task_match(requester_id, task_id):
            return "Sorry, your requester_id and task_id do not match"


        question_name = args['question_name']
        worker_platform_id = args['worker_id']
        worker_source = args['worker_source']
        value = args['value']
        is_alive = args['is_alive']

        requester = Requester.objects.get(id = requester_id)
        task = Task.objects.get(id = task_id)
        question = Question.objects.get(name = question_name,
                                        task = task)

        if not str(question.task.id) == task_id:
            return "Sorry, your question and task are inconsistent"
            
        
        worker = get_or_insert_worker(worker_platform_id, worker_source)
        if worker == None:
            return "You have not entered a valid worker source. It must be one of: [mturk,] "
        
        answers = Answer.objects(question = question,
                                worker = worker,
                                status = 'Assigned')
        
        if len(answers) == 0:
            answer = Answer(question = question,
                            task = task,
                            requester = requester,
                            worker = worker,
                            assign_time = None,
                            is_alive = is_alive)
            #REDIS update
            #this answer was not assigned by our system
            #Hack, might have to update bookkeeping for every strategy here
            #If the answer was not assigned by our system, should it count?
            task_queue_var = redis_get_task_queue_var(task_id, 'min_answers')
            #Check if the question is in the queue.
            #If not, don't need to do anything.
            #If it is, increment the count.
            pipe = app.redis.pipeline()
            while 1:
                try:
                    pipe.watch(task_queue_var)
                    if not pipe.zscore(task_queue_var,
                                       str(question.id)) == None:
                        pipe.zincrby(task_queue_var, str(question.id), 1)
                    if (pipe.zscore(task_queue_var,str(question.id)) >=
                        question.answers_per_question):
                        pipe.zrem(task_queue_var,str(question.id))
                    break
                except WatchError:
                    continue
                finally:
                    pipe.reset()


        else:
            #XXX assuming worker only assigned to particular question once?
            assert len(answers) == 1
            answer = answers[0]

            
        answer.complete_time = datetime.datetime.now()
        answer.value = value
        answer.status = 'Completed'

        answer.save()
        
        return {'value' : answer.value}

class AnswerApi(Resource):
    def get(self, answer_id):
        """
        Get data of specific answer.
        """
        answer = Answer.objects.get_or_404(id=answer_id)
        if answer:
            return {'answer_id' : str(answer.id),
                    'value' : answer.value,
                    'question_id' : str(answer.question.id),
                    'worker_id' : str(answer.worker.id)}
        else:
            return answer
