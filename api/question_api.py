from app import app
from redis_util import *
from flask.ext.restful import reqparse, abort, Api, Resource
import flask.ext.restful.inputs
from flask.ext.security import login_required, current_user, auth_token_required
import schema.question
from schema.task import Task
from schema.requester import Requester
import schema.answer
import json
import random
from util import requester_token_match, requester_token_match_and_task_match, requeue, requeueHelper
from mongoengine.queryset import DoesNotExist
from redis.exceptions import WatchError

question_parser = reqparse.RequestParser()
question_parser.add_argument('requester_id', type=str, required=True)
question_parser.add_argument('question_name', type=str, required=True)
question_parser.add_argument('question_description', type=str, required=True)
question_parser.add_argument('task_id', type=str, required=True)
question_parser.add_argument('question_data', type=str, required=False)
question_parser.add_argument('valid_answers', type=list, location='json', required=False)
question_parser.add_argument('answers_per_question', type=int, required=False,
                             default = 1)
question_parser.add_argument('unique_workers', type=bool, required=False,
                             default = True)


question_get_parser = reqparse.RequestParser()
question_get_parser.add_argument('requester_id', type=str, required=True)
question_get_parser.add_argument('task_id', type=str, required=False)


question_requeue_parser = reqparse.RequestParser()
question_requeue_parser.add_argument('requester_id', type=str, required=False)
question_requeue_parser.add_argument('task_id', type=str, required=False)
question_requeue_parser.add_argument('question_ids', type=list,
                                     location='json',required=False)
question_requeue_parser.add_argument('worker_ids', type=list,
                                     location='json',required=False)
question_requeue_parser.add_argument('worker_source', type=str,
                                     required=False)
question_requeue_parser.add_argument('strategy', type=str, required=False)



class QuestionApi(Resource):
    def get(self, question_id):
        """
        Get data of specific question.
        """
        question = schema.question.Question.objects.get_or_404(id=question_id)
        if question:
            return {'name': question.name,
                    'description': question.description}
        else:
            return question

class QuestionListApi(Resource):

    @auth_token_required
    def get(self):
        """
        Get list of all questions for a given task_id, or for a requester.
        """
        args = question_get_parser.parse_args()
                
        task_id = args['task_id']
        requester_id = args['requester_id']
        
        if not requester_token_match(requester_id):
            return {"error" : "Sorry, your api token is not correct"}

        if task_id:
            if not requester_token_match_and_task_match(requester_id, task_id):
                return {"error" : "Sorry, your task_id is not correct"}
            task = Task.objects.get_or_404(id = task_id)
            questions = schema.question.Question.objects(
                task = task)

        else:
            requester = Requester.objects.get_or_404(id = requester_id)
            questions = schema.question.Question.objects(
                requester = requester)

        return json.loads(questions.to_json())

    @auth_token_required
    def put(self):
        """
        Create a new question.
        """
        args = question_parser.parse_args()

        question_name = args['question_name']
        question_description = args['question_description']
        answers_per_question = args['answers_per_question']

        # optional args (default to empty)
        question_data = args.get('question_data', "")
        valid_answers = args.get('valid_answers', [])
        unique_workers = args['unique_workers']


        # check references
        requester_id = args['requester_id']

        task_id = args['task_id']
        if not requester_token_match_and_task_match(requester_id, task_id):
            return {"error" : "Sorry, your task_id is not correct"}

        task = schema.task.Task.objects.get(id=task_id)
        requester = schema.requester.Requester.objects.get(
            id=requester_id)


        questionDocument = schema.question.Question(
            name = question_name,
            description = question_description, 
            data = question_data,
            valid_answers = valid_answers, 
            task = task, requester = requester,
            answers_per_question = answers_per_question,
            unique_workers = unique_workers)

        questionDocument.save()

        #REDIS update add this question to the queue
        app.redis.zadd(redis_get_task_queue_var(task_id, 'min_answers'),
                       0,
                       str(questionDocument.id))

        return {'question_id' : str(questionDocument.id)}


class QuestionRequeueApi(Resource):

    #Requeue an assignment because a worker never did it
    #This should be called when the time for a assignment expires.
    #That means putting it back on the queue if it's not on the queue.
    @auth_token_required
    def post(self):
        
        args = question_requeue_parser.parse_args()

        #preliminary checks. make sure all ids exist, the workers have
        #been assigned to the question, and the questions are in the task.
        
        task_id = args['task_id']
        requester_id = args['requester_id']

        if not requester_token_match_and_task_match(requester_id, task_id):
            return {"error" : "Sorry, your task_id is not correct"}

        question_ids = args['question_ids']
        worker_ids = args['worker_ids']

        worker_source = args['worker_source']
        strategy = args['strategy']

                    
        return requeueHelper(task_id, requester_id, question_ids,
                       worker_ids, worker_source, strategy)


answer_get_parser = reqparse.RequestParser()
#answer_get_parser.add_argument('requester_id', type=str, required=True)
answer_get_parser.add_argument('question_id', type=str, required=False)
answer_get_parser.add_argument('completed',
                               type=flask.ext.restful.inputs.boolean,
                               required=False,
                               default = True)
#answer_get_parser.add_argument('assigned',
#                               type=flask.ext.restful.inputs.boolean,
#                               required=False,
#                               default = True)
class QuestionAnswersApi(Resource):
    def get(self):
        """
        Get all answers to a given question.
        """
        args = answer_get_parser.parse_args()
        #requester_id = args['requester_id']
        question_id = args['question_id']
        completed = args['completed']
        #assigned = args['assigned']

        if completed:
            answers = schema.answer.Answer.objects(question=question_id,
                                                   status='Completed')
        else:
            answers = schema.answer.Answer.objects(question=question_id)
            
        return json.loads(answers.to_json())
                                                                                                                                                                                      
