import sys, traceback
from flask import request
from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
from schema.answer import Answer
from schema.question import Question
from schema.task import Task
from schema.requester import Requester
from flask.json import jsonify
from util import requester_token_match, requester_token_match_and_task_match
import json
import datetime
from app import app

task_parser = reqparse.RequestParser()
task_parser.add_argument('requester_id', type=str, required=True)
task_parser.add_argument('task_name', type=str, required=True)
task_parser.add_argument('task_description', type=str, required=True)
task_parser.add_argument('questions', type=list, location='json',
                         required=False)
task_parser.add_argument('data', type=str, required=False)
task_parser.add_argument('global_answer_callback', type=str, required=False,
                         default = None)
task_parser.add_argument('answers_per_question', type=int, required=False,
                         default = 1)
task_parser.add_argument('total_task_budget', type=int, required=False,
                         default = -1)


tasklistapi_get_parser = reqparse.RequestParser()
tasklistapi_get_parser.add_argument('requester_id', type=str, required=True)

set_budget_parser = reqparse.RequestParser()
set_budget_parser.add_argument('requester_id', type=str, required=True)
set_budget_parser.add_argument('task_id', type=str, required=True)
set_budget_parser.add_argument('answers_per_question', type=int, required=False)
set_budget_parser.add_argument('total_task_budget', type=int, required=False)

delete_task_parser = reqparse.RequestParser()
delete_task_parser.add_argument('requester_id', type=str, required=True)
delete_task_parser.add_argument('task_id', type=str, required=True)



#TODO make this a blueprint
#@bp_tasks.route('/tasks', methods=['POST'])
#@app.route('/tasks', methods=['POST'])
#@auth_token_required
#def post_new_task():
#    return "YOUR TOKEN SHOULD MATCH: %s" %current_user.get_auth_token()

class TaskListApi(Resource):

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
        task_data = args['data']
        task_global_answer_callback = args['global_answer_callback']
        total_task_budget = args['total_task_budget']
        
        if questions is None:
            questions = []
        requester = Requester.objects.get_or_404(id = requester_id)
        
        # Save the task first so we can add questions with task id
        task = Task(
            name = task_name,
            description = task_description,
            requester = requester,
            data = task_data,
            global_answer_callback = task_global_answer_callback,
            total_task_budget = total_task_budget)

        #taskDocument.save()
        # Add questions to db
        #TODO arguments are not checked!
        questionDocuments = []
        for question in questions:
            question_name = question['question_name']
            question_description = question['question_description']

            question_data = question.get('question_data',"")
            valid_answers = question.get('valid_answers',[])

            #print question_name

            questionDocument = Question(name = question_name,
                                        description = question_description,
                                        data = question_data,
                                        valid_answers = valid_answers,
                                        task = task,
                                        requester = requester,
                                        answers_per_question =
                                        answers_per_question)

            questionDocuments.append(questionDocument)

        #If the requester provided a function, test it to see that
        #it doesn't break. First create an answer, the
        #call the function, then delete the question,
        #then delete the task data.
        if not task.global_answer_callback == None:
            try:
                answer = Answer(question = question,
                                task = task,
                                requester = requester,
                                worker = None,
                                assign_time = None,
                                is_alive = False,
                                complete_time = datetime.datetime.now(),
                                value = 'test',
                                status = 'Completed')
            
                question = questionDocuments[0]
                new_questions = []
                new_task_data = None
                                
                exec(task.global_answer_callback)
                
            
            except Exception as err:
                error_class = err.__class__.__name__                 
                detail = err.args[0]
                cl, exc, tb = sys.exc_info()
                line_number = traceback.extract_tb(tb)[-1][1]
                return 'Sorry, your callback threw an exception. %s %s %s ' % (
                    error_class, detail, line_number)

        
        #Only save the task and the questions after loading all the questions
        #and making sure there are no errors
        task.save()

        
        for questionDocument in questionDocuments:
            try:
                questionDocument.save()
            except Exception as err:
                error_class = err.__class__.__name__
                print error_class
                sys.stdout.flush()
                
                detail = err.args[0]
                print detail
                sys.stdout.flush()
                
                cl, exc, tb = sys.exc_info()
                line_number = traceback.extract_tb(tb)[-1][1]

                
        return {'task_id' : str(task.id) }

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
        task_id = args['task_id']

        if not requester_token_match_and_task_match(requester_id, task_id):
            return "Sorry, your api token is not correct"

        answers_per_question = args['answers_per_question']
        total_task_budget = args['total_task_budget']

        if not answers_per_question == None:
            questions = Question.objects(task=task_id)
            for question in questions:
                question.answers_per_question = answers_per_question
                question.save()

        if not total_task_budget == None:
            task = Task.objects.get_or_404(id=task_id)
            task.total_task_budget = total_task_budget
            task.save()

        if answers_per_question:
            if not total_task_budget:
                return "Task %s now allows %d answers per question" % (
                    task_id, answers_per_question)
            else:
                return "Task %s now allows %d answers per question and has a total task budget of %d" % (
                    task_id, answers_per_question, total_task_budget)
        else:
            if total_task_budget:
                return "Task %s now has a total task budget of %d" % (
                    task_id, total_task_budget)

                
        


class TaskDelete(Resource):
    @auth_token_required
    def post(self):

        args = delete_task_parser.parse_args()

        requester_id = args['requester_id']
        task_id = args['task_id']

        if not requester_token_match_and_task_match(requester_id, task_id):
            return "Sorry, your api token is not correct"
 
        Answer.objects(task = task_id).delete()
        Question.objects(task = task_id).delete()
        Task.objects.get(id = task_id).delete()

        return "Task %s deleted!" % task_id
