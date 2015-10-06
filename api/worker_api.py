from flask.ext.restful import reqparse, abort, Api, Resource
from schema.worker import Worker
from schema.answer import Answer
import json

worker_parser = reqparse.RequestParser()
worker_parser.add_argument('turk_id', type=str, required=True)

class WorkerApi(Resource):
    def get(self, worker_id):
        """
        Get data of specific worker.
        """
        worker = Worker.objects.get_or_404(id=worker_id)
        return json.loads(worker.to_json())

class WorkerListApi(Resource):
    def get(self):
        """
        Get list of all workers.
        """
        return json.loads(Worker.objects.to_json())
    def put(self):
        """
        Create a new worker.
        """
        args = worker_parser.parse_args()
        turk_id = args['turk_id']

        workerDocument = Worker(turk_id)
        workerDocument.save()

        return {'worker_id' : str(workerDocument.id)}

class WorkerAnswersApi(Resource):
    def get(self, worker_id):
        """
        Get all answers by the given worker.
        """
        answers = Answer.objects(worker=worker_id)
        return json.loads(answers.to_json())
