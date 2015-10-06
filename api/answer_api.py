from flask.ext.restful import reqparse, abort, Api, Resource
from flask import url_for
from schema.answer import Answer
from schema.question import Question
from schema.worker import Worker
import json

answer_parser = reqparse.RequestParser()
answer_parser.add_argument('question_id', type=str, required=True)
answer_parser.add_argument('worker_id', type=str, required=True)
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
        
        question_id = args['question_id']
        worker_id = args['worker_id']
        value = args['value']
        
        question = Question.objects.get_or_404(id=question_id)
        worker = Worker.objects.get_or_404(id=worker_id)

        answer = Answer(value = value,
                        question = question,
                        worker = worker)

        answer.save()
        
        #return "Answer inserted"
        #TODO what to return
        return {'answer_id' : str(answer.id),
                'value' : answer.value}

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
