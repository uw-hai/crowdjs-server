import sys, traceback
from flask import request
from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
from schema.question import Question
from schema.task import Task
from schema.requester import Requester
from flask.json import jsonify
import json
from app import app

task_parser = reqparse.RequestParser()
task_parser.add_argument('requester_id', type=str, required=True)
task_parser.add_argument('task_name', type=str, required=True)
task_parser.add_argument('task_description', type=str, required=True)
task_parser.add_argument('questions', type=list, location='json', required=False)


#TODO make this a blueprint
#@bp_tasks.route('/tasks', methods=['POST'])
#@app.route('/tasks', methods=['POST'])
#@auth_token_required
#def post_new_task():
#    return "YOUR TOKEN SHOULD MATCH: %s" %current_user.get_auth_token()

class TaskListApi(Resource):
    # Must be logged in to 
    decorators = [login_required]

    def get(self):
        """
        Get list of all tasks.
        """
        tasks = Task.objects
        return json.loads(tasks.to_json())

    def put(self):
        username = current_user
        print username
        """
        Create a new task.
        """
        args = task_parser.parse_args()
        requester_id = args['requester_id']
        task_name = args['task_name']
        task_description = args['task_description']
        questions = args['questions']
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
                                        requester = requester)

            questionDocuments.append(questionDocument)

        #Only save the questions after loading all the questions
        #and making sure there are no errors
        for questionDocument in questionDocuments:
            questionDocument.save()

        # Want to be able to answer included questions later, so need references to them
        # XXX assuming unique question names! (i.e. it would make more sense to use those
        # instead of the database IDs)
        questionDocumentIDs = dict()
        for questionDocument in questionDocuments:
            questionDocumentIDs[questionDocument.name] = str(questionDocument.id)
        
        return {'task_id' : str(taskDocument.id), 'question_ids' : questionDocumentIDs}

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
