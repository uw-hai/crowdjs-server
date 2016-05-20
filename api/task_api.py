from app import app
from redis_util import redis_get_worker_assignments_var, redis_get_task_queue_var
import sys, traceback
from flask import request
from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
from schema.answer import Answer
from schema.question import Question
from schema.task import Task
from schema.requester import Requester
from schema.worker import Worker
from flask.json import jsonify
from util import requester_token_match, requester_token_match_and_task_match, clear_task_from_redis
import json
import datetime

task_parser = reqparse.RequestParser()
task_parser.add_argument('requester_id', type=str, required=True)
task_parser.add_argument('task_name', type=str, required=True)
task_parser.add_argument('task_description', type=str, required=True)
task_parser.add_argument('questions', type=list, location='json',
                         required=False)
task_parser.add_argument('data', type=str, required=False)
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
delete_task_parser.add_argument('task_id', type=str, required=False)


clear_redis_parser = reqparse.RequestParser()
clear_redis_parser.add_argument('requester_id', type=str, required=True)
clear_redis_parser.add_argument('task_id', type=str, required=False)




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

        args:
            questions (optional list): 
                Questions from this list will be inserted  and
                their corresponding IDs will be returned in the same order.
                i.e. questions= [A,B,C] -> return [A.id, B.id, C.id]
        """

        args = task_parser.parse_args()
        
        requester_id = args['requester_id']
        if not requester_token_match(requester_id):
            return "Sorry, your api token is not correct"
        
        task_name = args['task_name']
        task_description = args['task_description']
        questions = args['questions']
        task_answers_per_question = args['answers_per_question']
        task_data = args['data']
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
            total_task_budget = total_task_budget)

        questionDocuments = []
        for question in questions:
            question_name = question['question_name']
            question_description = question['question_description']

            question_data = question.get('question_data',"")
            valid_answers = question.get('valid_answers',[])
            answers_per_question = question.get('answers_per_question',
                                                task_answers_per_question)
            unique_workers = question.get('unique_workers', True)


            questionDocument = Question(name = question_name,
                                        description = question_description,
                                        data = question_data,
                                        valid_answers = valid_answers,
                                        task = task,
                                        requester = requester,
                                        answers_per_question =
                                        answers_per_question,
                                        unique_workers = unique_workers)

            questionDocuments.append(questionDocument)
        
        #Only save the task and the questions after loading all the questions
        #and making sure there are no errors
        task.save()
        
        question_id_list = []
        for questionDocument in questionDocuments:
            try:
                questionDocument.save()
                #REDIS update 
                # -add this question to the queue
                app.redis.zadd(redis_get_task_queue_var(task.id, 'min_answers'), 0, str(questionDocument.id))
                question_id_list.append(str(questionDocument.id))
            except Exception as err:
                error_class = err.__class__.__name__
                print error_class
                sys.stdout.flush()
                
                detail = err.args[0]
                print detail
                sys.stdout.flush()
                
                cl, exc, tb = sys.exc_info()
                line_number = traceback.extract_tb(tb)[-1][1]

                
        ret = {'task_id' : str(task.id)}
        if questions:
            # if batch of questions was inserted,
            # include list of their corresponding question IDs
            ret['question_ids'] = question_id_list
        return ret

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

        if answers_per_question:
            questions = Question.objects(task=task_id)
            task_queue_var = redis_get_task_queue_var(task_id, 'min_answers')
            for question in questions:

                previous_answers_per_question = question.answers_per_question
                diff = answers_per_question - previous_answers_per_question

                if diff > 0 and (app.redis.zscore(task_queue_var,
                                                 str(question.id)) == None):
                    app.redis.zadd(task_queue_var,
                                   previous_answers_per_question,
                                   str(question.id))
                if diff < 0 and app.redis.zscore(task_queue_var,
                                                 str(question.id)):
                    if (app.redis.zscore(task_queue_var, str(question.id)) >=
                        answers_per_question):
                        app.redis.zrem(task_queue_var, str(question.id))
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

        if task_id:
            if not requester_token_match_and_task_match(requester_id, task_id):
                return {'error' : 'Sorry, you cannot delete that task'}
 
            Answer.objects(task = task_id).delete()
            Question.objects(task = task_id).delete()
            Task.objects.get(id = task_id).delete()
            
            return {'success' : 'Task %s deleted!' % task_id}

        else:
            requester = Requester.objects.get_or_404(id = requester_id)
            tasks = Task.objects(requester = requester)
            for task in tasks:
                Answer.objects(task = task).delete()
                Question.objects(task = task).delete()
            tasks.delete()
                
            return {'success' :
                    'All tasks for requester %s deleted!' % requester_id}


class TaskClearRedis(Resource):

    #This should eventually only be allowed to administrators.
    @auth_token_required
    def post(self):

        args = clear_redis_parser.parse_args()

        requester_id = args['requester_id']
        task_id = args['task_id']
        
        if task_id:
            if not requester_token_match_and_task_match(requester_id, task_id):
                return {'error' : 'Sorry, you cannot clear redis for this task'}

            (num_questions_deleted,
             worker_assignments_deleted) = clear_task_from_redis(task_id)
                
            return {'success' : 'Task %s cleared from redis! %d questions removed from queue and %d worker assignment sets removed.' % (
                task_id, num_questions_deleted, worker_assignments_deleted) }

        else:
            requester = Requester.objects.get_or_404(id = requester_id)
            tasks = Task.objects(requester = requester)

            total_questions_deleted = 0
            total_assignments_deleted = 0
            
            for task in tasks:
                (num_questions_deleted,
                 worker_assignments_deleted) = clear_task_from_redis(task.id)
                total_questions_deleted += num_questions_deleted
                total_assignments_deleted += worker_assignments_deleted
            return {
                'success' :
                'All tasks for requester %s cleared from redis! %d questions removed from queue and %d worker assignment sets removed.' % (
                    requester_id,
                    total_questions_deleted, total_assignments_deleted)}
