from flask.ext.restful import reqparse, abort, Api, Resource
import schema.question
import schema.task
import schema.requester
import json


question_parser = reqparse.RequestParser()
question_parser.add_argument('requester_id', type=str, required=True)
question_parser.add_argument('question_name', type=str, required=True)
question_parser.add_argument('question_description', type=str, required=True)
#TODO what is question_data for? not in the schema...
question_parser.add_argument('question_data', type=str, required=True)
question_parser.add_argument('task_id', type=str, required=True)

class QuestionApi(Resource):
    def get(self, question_id):
        """
        Get data of specific question.
        """
        question = schema.question.Question.objects.get_or_404(id=question_id)
        if question:
            return {'name': question.name,
                    'description': question.description}
        else:
            return question

class QuestionListApi(Resource):
    def get(self):
        """
        Get list of all questions.
        """
        questions = schema.question.Question.objects
        return json.loads(questions.to_json())

    def put(self):
        """
        Create a new question.
        """
        args = question_parser.parse_args()

        question_name = args['question_name']
        question_description = args['question_description']

        requester_id = args['requester_id']
        requester = schema.requester.Requester.objects.get_or_404(id=requester_id)

        task_id = args['task_id']
        task = schema.task.Task.objects.get_or_404(id=task_id)

        questionDocument = schema.question.Question(name = question_name, description = question_description, task = task, requester = requester)

        questionDocument.save()

        return {'question_id' : str(questionDocument.id)}
