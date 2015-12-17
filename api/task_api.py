import sys, traceback
from flask import request
from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
from schema.question import Question
from schema.task import Task
from schema.requester import Requester
from flask.json import jsonify
from util import requester_token_match
import json
from app import app

task_parser = reqparse.RequestParser()
task_parser.add_argument('requester_id', type=str, required=True)
task_parser.add_argument('task_name', type=str, required=True)
task_parser.add_argument('task_description', type=str, required=True)
task_parser.add_argument('questions', type=list, location='json', required=False)
task_parser.add_argument('answers_per_question', type=int, required=False,
                         default = 1)

tasklistapi_get_parser = reqparse.RequestParser()
tasklistapi_get_parser.add_argument('requester_id', type=str, required=True)

set_budget_parser = reqparse.RequestParser()
set_budget_parser.add_argument('requester_id', type=str, required=True)
set_budget_parser.add_argument('task_id', type=str, required=True)
set_budget_parser.add_argument('answers_per_question', type=int, required=True)



#TODO make this a blueprint
#@bp_tasks.route('/tasks', methods=['POST'])
#@app.route('/tasks', methods=['POST'])
#@auth_token_required
#def post_new_task():
#    return "YOUR TOKEN SHOULD MATCH: %s" %current_user.get_auth_token()

class TaskListApi(Resource):
    # Must be logged in to 
    decorators = [login_required]

    @auth_token_required
    def get(self):
        """
        Get list of all tasks.
        """
        args = tasklistapi_get_parser.parse_args()
        requester_id = args['requester_id']
        
        if not requester_token_match(requester_id):
            return "Sorry, your api token is not correct"

        tasks = Task.objects(requester = requester_id)
        return json.loads(tasks.to_json())

    @auth_token_required
    def put(self):
        """
        Create a new task.
        """
        args = task_parser.parse_args()
        
        requester_id = args['requester_id']
        if not requester_token_match(requester_id):
            return "Sorry, your api token is not correct"
        
        task_name = args['task_name']
        task_description = args['task_description']
        questions = args['questions']
        answers_per_question = args['answers_per_question']
        
        if questions is None:
            questions = []

        requester = Requester.objects.get_or_404(id = requester_id)

        # Save the task first so we can add questions with task id
        taskDocument = Task(name = task_name,
                            description = task_description,
                            requester = requester)
        taskDocument.save()

        # Add questions to db
        #TODO arguments are not checked!
        questionDocuments = []
        for question in questions:
            question_name = question['question_name']
            question_description = question['question_description']

            #optional fields
            question_data = question.get('question_data',"")
            valid_answers = question.get('valid_answers',[])

            questionDocument = Question(name = question_name,
                                        description = question_description,
                                        data = question_data,
                                        valid_answers = valid_answers,
                                        task = taskDocument,
                                        requester = requester,
                                        answers_per_question =
                                        answers_per_question)

            questionDocuments.append(questionDocument)

        #Only save the questions after loading all the questions
        #and making sure there are no errors
        for questionDocument in questionDocuments:
            questionDocument.save()


        
        return {'task_id' : str(taskDocument.id) }

class TaskApi(Resource):
    def get(self, task_id):
        """
        Get data of specific task.
        """
        print "Getting Task"
        task = Task.objects.get_or_404(id=task_id)
        questions = Question.objects(task=task_id)
        #TODO currently dump in the task's questions - maybe think this through more
        d = json.loads(task.to_json())
        d['questions'] = json.loads(questions.to_json())
        return d

class TaskQuestionsApi(Resource):
    def get(self, task_id):
        """
        Get all questions contained in the given task.
        """
        questions = Question.objects(task=task_id)
        return json.loads(questions.to_json())


class TaskSetBudget(Resource):

    @auth_token_required
    def post(self):
        args = set_budget_parser.parse_args()
                
        requester_id = args['requester_id']
        if not requester_token_match(requester_id):
            return "Sorry, your api token is not correct"

        task_id = args['task_id']
        answers_per_question = args['answers_per_question']

        questions = Question.objects(task=task_id)

        for question in questions:
            question.answers_per_question = answers_per_question
            question.save()
            
        return "Task %s now allows %d answers per question" % (
            task_id, answers_per_question)
