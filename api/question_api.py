from app import app
from redis_util import *
from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
import schema.question
from schema.task import Task
from schema.requester import Requester
import schema.answer
import json
import random
from util import requester_token_match, requester_token_match_and_task_match


question_parser = reqparse.RequestParser()
question_parser.add_argument('requester_id', type=str, required=True)
question_parser.add_argument('question_name', type=str, required=True)
question_parser.add_argument('question_description', type=str, required=True)
question_parser.add_argument('task_id', type=str, required=True)
question_parser.add_argument('question_data', type=str, required=False)
question_parser.add_argument('valid_answers', type=list, location='json', required=False)


question_get_parser = reqparse.RequestParser()
question_get_parser.add_argument('requester_id', type=str, required=True)
question_get_parser.add_argument('task_id', type=str, required=False)

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

    def put(self):
        """
        Create a new question.
        """
        args = question_parser.parse_args()

        question_name = args['question_name']
        question_description = args['question_description']

        # optional args (default to empty)
        question_data = args.get('question_data', "")
        valid_answers = args.get('valid_answers', [])

        # check references
        requester_id = args['requester_id']
        requester = schema.requester.Requester.objects.get_or_404(
            id=requester_id)

        task_id = args['task_id']
        task = schema.task.Task.objects.get_or_404(id=task_id)

        questionDocument = schema.question.Question(
            name = question_name,
            description = question_description, 
            data = question_data,
            valid_answers = valid_answers, 
            task = task, requester = requester)

        questionDocument.save()

        #REDIS update add this question to the queue
        app.redis.zadd(redis_get_task_queue_var(task_id, 'min_answers'), 0, question_name)

        return {'question_id' : str(questionDocument.id)}

class QuestionAnswersApi(Resource):
    def get(self, question_id):
        """
        Get all answers to a given question.
        """
        answers = schema.answer.Answer.objects(question=question_id)
        return json.loads(answers.to_json())
