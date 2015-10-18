from flask.ext.restful import reqparse, abort, Api, Resource
import schema.question
import schema.task
import schema.requester
import schema.answer
import json
import random

nextq_parser = reqparse.RequestParser()
nextq_parser.add_argument('worker_id', type=str, required=True)
nextq_parser.add_argument('task_id', type=str, required=True)
nextq_parser.add_argument('strategy', type=str, required=False, default='random')

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
        task_id = args['task_id']

        task = schema.task.Task.objects.get_or_404(id=task_id)
        
        worker_id = args['worker_id']
        if worker_id is None:
            return "missing worker_id"

        if strategy == 'min_answers':
            question = self.min_answers(task_id, worker_id)
        elif strategy == 'random':
            question = self.random_choice(task_id, worker_id)
        else:
            return "error: INVALID STRATEGY"

        return {'question_id' : str(question.id)}

    def random_choice(self, task_id, worker_id):
        task = schema.task.Task.objects.get_or_404(id=task_id)
        questions = schema.question.Question.objects(task=task)
        qlist = list(questions)
        return random.choice(qlist)

    def min_answers(self, task_id, worker_id):
        """
        Assumes that task and worker IDs have been checked.
        """
        #XXX First pass: assign question with the least number of answers

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
            answers = schema.answer.Answer.objects(question=question)
            print question.id, len(answers)
            if len(answers) < min_answers:
                chosen_question = question
                min_answers = len(answers)

        question = chosen_question
        return question
