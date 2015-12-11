from flask.ext.restful import reqparse, abort, Api, Resource
from flask import url_for
from schema.answer import Answer
from schema.question import Question
from schema.worker import Worker
from util import get_or_insert_worker
import datetime
import json

answer_parser = reqparse.RequestParser()
answer_parser.add_argument('question_name', type=str, required=True)
answer_parser.add_argument('worker_id', type=str, required=True)
answer_parser.add_argument('worker_source', type=str, required=True)
answer_parser.add_argument('value', type=str, required=True)

class AnswerListApi(Resource):
    def get(self):
        """
        Get list of all answers.
        """
        answers = Answer.objects
        return json.loads(answers.to_json())
    def put(self):
        """
        Create a new answer.
        """
        args = answer_parser.parse_args()
        
        question_name = args['question_name']
        worker_id = args['worker_id']
        worker_source = args['worker_source']
        value = args['value']
        
        question = Question.objects.get_or_404(name=question_name)
        
        worker = get_or_insert_worker(worker_id, worker_source)
        if worker == None:
            return "You have not entered a valid worker source. It must be one of: [mturk,] "
        
        answers = Answer.objects(question = question,
                                worker = worker,
                                status = 'Assigned')
        
        if len(answers) == 0:
            answer = Answer(question = question,
                            worker = worker,
                            status = 'Completed',
                            assign_time = None)
        else:
            answer = answers[0]
        
        answer.complete_time = datetime.datetime.now()
        answer.value = value
        answer.status = 'Completed'

        answer.save()
        
        #return "Answer inserted"
        #TODO what to return
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
