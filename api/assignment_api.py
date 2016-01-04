from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import login_required, current_user, auth_token_required
import datetime
import schema.question
import schema.task
import schema.requester
import schema.answer
import json
import random
from util import requester_token_match, requester_token_match_and_task_match, get_or_insert_worker, get_alive_answers, requester_task_match


nextq_parser = reqparse.RequestParser()
#TODO:
#The worker id should not be required
nextq_parser.add_argument('worker_id', type=str, required=True)
nextq_parser.add_argument('worker_source', type=str, required=True)
nextq_parser.add_argument('task_id', type=str, required=True)
nextq_parser.add_argument('requester_id', type=str, required=True)
nextq_parser.add_argument('strategy', type=str, required=False,
                          default='random')
nextq_parser.add_argument('preview', type=bool, required=False,
                          default=False)


class NextQuestionApi(Resource):
    """
    Usage:
    GET /url with JSON={worker_id:XXX, task_id:XXX [,strategy:XXX]}
    """

    def get(self):

        """
        Assign a question from the given task to the given worker.
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
        worker_id = args['worker_id']
        worker_source = args['worker_source']

        worker = get_or_insert_worker(worker_id, worker_source)
        if worker == None:
            return "You have not entered a valid worker source. It must be one of: [mturk,] "

        if strategy == 'min_answers':   
            question = self.min_answers(task_id, worker_id)
        elif strategy == 'random':
            question = self.random_choice(task_id, worker_id)
        else:
            return "error: INVALID STRATEGY"

        if question == None:
            return None

        if not preview:
            answer = schema.answer.Answer(question = question,
                                          task = task,
                                      requester=requester,
                                          worker = worker,
                                          status = 'Assigned',
                                          assign_time=datetime.datetime.now,
                                          is_alive = True)
            
            answer.save()
        
        return {'question_name' : str(question.name)}

    ####
    # NOT FULLY TESTED
    ####
    def random_choice(self, task_id, worker_id):
        task = schema.task.Task.objects.get_or_404(id=task_id)
        questions = schema.question.Question.objects(task=task)
        qlist = list(questions)

        filtered_qlist = filter(
            lambda q:len(get_alive_answers(q)) < q.answers_per_question,
            qList)

        print "LISTS"
        print qlist
        print filtered_qlist
        if len(filtered_qlist) == 0:
            return None
        question = random.choice(filtered_qlist)
        return question

    def min_answers(self, task_id, worker_id):
        """
        Assumes that task and worker IDs have been checked.
        """

        task = schema.task.Task.objects.get_or_404(id=task_id)

        # XXX join across Mongo documents yuck
        # SQL equivalent:
        # SELECT QUESTION_ID, COUNT(*) as num_answers FROM QUESTIONS q, ANSWERS a
        # WHERE q.id = a.qid GROUP BY q.id ORDER BY num_answers

        # Find first question with the fewest answers
        # TODO tiebreaker
        questions = schema.question.Question.objects(task=task)
        min_answers = float("inf") # +infinity
        chosen_question = None
        for question in questions:

            answers = get_alive_answers(question)
            if len(answers) >= question.answers_per_question:
                continue
            if len(answers) < min_answers:
                chosen_question = question
                min_answers = len(answers)

        question = chosen_question
        return question
