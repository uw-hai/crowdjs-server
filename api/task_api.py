from flask.ext.restful import reqparse, abort, Api, Resource
from schema.question import Question
from schema.task import Task
from schema.requester import Requester
import json

task_parser = reqparse.RequestParser()
task_parser.add_argument('reqester_id', type=str, required=True)
task_parser.add_argument('task_name', type=str, required=True)
task_parser.add_argument('task_description', type=str, required=True)
task_parser.add_argument('questions', type=str, required=True)

class TaskApi(Resource):
    def put(self):
        args = task_parser.parse_args()
        
        requester_id = args['requester_id']
        task_name = args['task_name']
        task_description = args['task_description']

        questions = json.loads(args['questions'])

        requester = Requester.objects.get_or_404(id = requester_id)
        
        questionDocuments = []
        for question in questions:
            question_name = question['question_name']
            question_description = question['question_description']
            
            questionDocument = Question(name = question_name,
                                        description = question_description,
                                        requester = requester)
            questionDocuments.append(questionDocument)

        #Only save the questions after loading all the questions
        #and making sure there are no errors
        for questionDocument in questionDocuments:
            questionDocument.save()

        taskDocument = Task(name = task_name,
                            description = task_description,
                            questions = questionDocuments,
                            requester = requester)
        taskDocument.save()

        return "Task Saved"
