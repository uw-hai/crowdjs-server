from flask.ext.restful import Resource
import schema.question

class QuestionApi(Resource):
    def get(self, question_id):
        question = schema.question.Question.objects.get_or_404(id=question_id)
        if question:
            return {'name': question.name,
                    'description': question.description}
        else:
            return question
