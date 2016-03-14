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
answer_parser.add_argument('call_gac', type=flask.ext.restful.inputs.boolean,
                           required=False,
                           default=True)

answer_get_parser = reqparse.RequestParser()
answer_get_parser.add_argument('requester_id', type=str, required=True)
answer_get_parser.add_argument('task_id', type=str, required=False)

class AnswerListApi(Resource):

    @auth_token_required
    def get(self):
        """
        Get list of all answers.
        """
        args = answer_get_parser.parse_args()
        requester_id = args['requester_id']
        task_id = args['task_id']
        if task_id == None:
            if not requester_token_match(requester_id):
                return "Sorry, your api token is not correct"
            requester = Requester.objects.get_or_404(id=requester_id)
            answers = Answer.objects(requester = requester)
        else:
            if not requester_token_match_and_task_match(requester_id, task_id):
                return "Sorry, your api token is not correct"

            requester = Requester.objects.get_or_404(id=requester_id)
            task = Task.objects.get_or_404(id=task_id)
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
        worker_id = args['worker_id']
        worker_source = args['worker_source']
        value = args['value']
        is_alive = args['is_alive']
        call_gac = args['call_gac']

        requester = Requester.objects.get(id = requester_id)
        task = Task.objects.get(id = task_id)
        question = Question.objects.get(name = question_name,
                                        task = task)

        if not str(question.task.id) == task_id:
            return "Sorry, your question and task are inconsistent"
            
        
        worker = get_or_insert_worker(worker_id, worker_source)
        if worker == None:
            return "You have not entered a valid worker source. It must be one of: [mturk,] "
        
        answers = Answer.objects(question = question,
                                worker = worker,
                                status = 'Assigned')
        #print "LEN ANSWERS"
        #print question.name
        #print worker.platform_id
        #print len(answers)
        #for a in Answer.objects:
        #    print a.id
        
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
            app.redis.zincrby(redis_get_task_queue_var(task_id, 'min_answers'), str(question.id), 1)

        else:
            #XXX assuming worker only assigned to particular question once?
            assert len(answers) == 1
            answer = answers[0]
        
        answer.complete_time = datetime.datetime.now()
        answer.value = value
        answer.status = 'Completed'

        answer.save()

        #Now run any code that the requester specified.
        if (not task.global_answer_callback == None and
            call_gac):
            try:
                new_questions = []
                new_task_data = None
                old_question_budget = None

                new_question_documents = []
                exec(task.global_answer_callback)
                for new_question_def in new_questions:
                    new_question_name = new_question_def['name']
                    new_question_description = new_question_def['description']
                    new_question_data = new_question_def['data']
                    new_question_task = new_question_def['task']
                    new_question_requester = new_question_def['requester']
                    new_question_apq = new_question_def[
                        'answers_per_question']

                    #If the question already exists, do not add it
                    if len(Question.objects(task=task,
                                            name=new_question_name)) > 0:
                        continue
                    
                    new_question = Question(
                        name = new_question_name,
                        description = new_question_description,
                        data = new_question_data,
                        task = new_question_task,
                        requester = new_question_requester,
                        answers_per_question = new_question_apq)
                    

                    new_question_documents.append(new_question)

                for new_question_document in new_question_documents:
                    new_question_document.save()

                    #REDIS Update
                    app.redis.zadd(redis_get_task_queue_var(task_id, 'min_answers'), 0, str(new_question_document.id))
                task.data = new_task_data
                task.save()

                if not old_question_budget == None:
                    #Set the answers_per_question of the old question
                    #to something specified in the callback. This
                    #allows you to turn off the old question.
                    question.answers_per_question = old_question_budget
                    question.save()
                
            except Exception as err:
                error_class = err.__class__.__name__
                detail = err.args[0]                
                cl, exc, tb = sys.exc_info()
                line_number = traceback.extract_tb(tb)[-1][1]
                return 'Sorry, your callback threw an exception. %s %s %s ' % (
                    error_class, detail, line_number)
        
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
