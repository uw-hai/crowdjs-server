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
answer_get_parser.add_argument('completed',
                               type=flask.ext.restful.inputs.boolean,
                               required=False,
                               default = True)
answer_get_parser.add_argument('assigned',
                               type=flask.ext.restful.inputs.boolean,
                               required=False,
                               default = True)

class AnswerListApi(Resource):

    @auth_token_required
    def get(self):
        """Get list of all answers.

        Can filter by specific task and/or whether answer is completed.

        :param str requester_id: your requester id.
        :param str task_id: optional. Get answers for only this task.
        :param bool completed: optional. Get only completed answers.
        :param bool assigned: optional. Get only answers that were assigned.
        """
        args = answer_get_parser.parse_args()
        requester_id = args['requester_id']
        task_id = args['task_id']
        completed = args['completed']
        assigned = args['assigned']
        
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
        """Create a new answer.

        :param str requester_id:
        :param str task_id:
        :param str question_name:
        :param str worker_platform_id:
        :param str worker_source:
        :param str value:
        :param bool is_alive: optional.
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
                                 value = value)
        if len(answers) > 0:
            return {'error' : 'Answer already in database'}

        answers = Answer.objects(question = question,
                                 worker = worker,
                                 status = 'Assigned')

        #If this answer was not assigned by our system, AND regardless
        #of whether the worker has answered it before and the question
        #allows for the same worker to answer it multiple times,
        #add it, and inform the
        #requester the question was unassigned
        #If the worker has answered it before AND
        #the question doesn't allow the same worker to answer it
        #multiple times, then disallow the insertion.
        if len(answers) == 0:
            answers = Answer.objects(question = question,
                                     worker = worker)
            if len(answers) > 1 and question.unique_workers:
                return {'error' : 'Worker already answered this question'}
            
            answer = Answer(question = question,
                            task = task,
                            requester = requester,
                            worker = worker,
                            assign_time = None,
                            is_alive = is_alive)
            answer.complete_time = datetime.datetime.now()
            answer.value = value
            answer.status = 'Completed'
            answer.save()
            
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

            return {'success' :
                    'Unassigned answer inserted. value: %s' % answer.value}

        else:
            answer = answers[0]
            
            answer.complete_time = datetime.datetime.now()
            answer.value = value
            answer.status = 'Completed'
            answer.save()
        return {'success' : answer.value}
        
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
