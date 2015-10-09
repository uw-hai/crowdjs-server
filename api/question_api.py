from flask.ext.restful import reqparse, abort, Api, Resource
import schema.question
import schema.task
import schema.requester
import schema.answer
import json


question_parser = reqparse.RequestParser()
question_parser.add_argument('requester_id', type=str, required=True)
question_parser.add_argument('question_name', type=str, required=True)
question_parser.add_argument('question_description', type=str, required=True)
question_parser.add_argument('task_id', type=str, required=True)
question_parser.add_argument('question_data', type=str, required=False)
question_parser.add_argument('valid_answers', type=list, location='json', required=False)

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

        # optional args (default to empty)
        question_data = args.get('question_data', "")
        valid_answers = args.get('valid_answers', [])

        # check references
        requester_id = args['requester_id']
        requester = schema.requester.Requester.objects.get_or_404(id=requester_id)

        task_id = args['task_id']
        task = schema.task.Task.objects.get_or_404(id=task_id)

        questionDocument = schema.question.Question(name = question_name, description = question_description, 
                data = question_data,
                valid_answers = valid_answers, 
                task = task, requester = requester)

        questionDocument.save()

        return {'question_id' : str(questionDocument.id)}

class QuestionAnswersApi(Resource):
    def get(self, question_id):
        """
        Get all answers to a given question.
        """
        answers = schema.answer.Answer.objects(question=question_id)
        return json.loads(answers.to_json())
