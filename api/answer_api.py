from flask.ext.restful import reqparse, abort, Api, Resource
from schema.answer import Answer
from schema.question import Question
from schema.requester import Requester
from schema.worker import Worker

answer_parser = reqparse.RequestParser()
answer_parser.add_argument('question_id', type=str, required=True)
answer_parser.add_argument('worker_id', type=str, required=True)
answer_parser.add_argument('value', type=str, required=True)

class AnswerApi(Resource):
    def put(self):
        args = answer_parser.parse_args()
        
        question_id = args['question_id']
        worker_id = args['worker_id']
        value = args['value']
        
        question = Question.objects.get_or_404(id=question_id)
        requester = question.requester
        worker = Worker.objects.get_or_404(id=worker_id)

        answer = Answer(value = value,
                        question = question,
                        worker = worker,
                        requester = requester)

        answer.save()                        

        question.worker_answers.append(answer)
        question.save()

        return "Answer inserted"

