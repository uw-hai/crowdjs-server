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
from redis.exceptions import WatchError


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

        """Assign a question from the given task to the given worker.

        :param str worker_id: worker's platform id
        :param str worker_source: i.e. mturk
        :param str task_id:
        :param str requester_id: id of requester who owns this task
        :param str strategy: optional, defaults to 'min_answers' assignment strategy. other choices: random, pomdp, ...
        :param bool preview: optional, if true then the question id will be returned but no assignment will be created.

        **Example response:**

        .. code-block:: json

            {
                "question_name" : "999999",
                "question_id" : "1234",
                "question_data" : "some q data"
            }

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
                    'question_id': str(current_assignment[0].question.id),
                    'question_data' : str(current_assignment[0].question.data)}

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
        return {'question_name' : str(question.name),
                'question_id' : str(question.id),
                'question_data' : str(question.data)}

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
        worker_assignments_var = redis_get_worker_assignments_var(task_id,
                                                                  worker_id)


        pipe = app.redis.pipeline()
        while 1:
            try:
                pipe.watch(task_questions_var)
                pipe.watch(worker_assignments_var)
                task_questions = pipe.zrange(task_questions_var, 0, -1)
                for question in task_questions:
                    #If the worker has not done it before, assign it.
                    #Otherwise, if the question allows for
                    #multiple answers from the same worker,
                    #assign it.
                    if not pipe.sismember(worker_assignments_var, question):
                        chosen_question = question
                        break
                    else:
                        question_obj = schema.question.Question.objects.get(
                            id=question)
                        if not question_obj.unique_workers:    
                            chosen_question = question
                            break
                    
                if chosen_question is None:
                    return None
                chosen_question_obj = schema.question.Question.objects.get(
                    id=chosen_question)
                
                pipe.sadd(worker_assignments_var, chosen_question)
                pipe.zincrby(task_questions_var, chosen_question, 1)
                
                #If this assignemnt causes the question to
                #reach its allocated budget,
                #Remove it from the queue.                        
                if (pipe.zscore(task_questions_var,chosen_question) >=
                    chosen_question_obj.answers_per_question):
                    pipe.zrem(task_questions_var, chosen_question)
                break
            except WatchError:
                continue
            finally:
                pipe.reset()
                
        return chosen_question_obj
