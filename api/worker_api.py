from flask.ext.restful import reqparse, abort, Api, Resource
from schema.worker import Worker
import json

worker_get_parser = reqparse.RequestParser()
worker_get_parser.add_argument('worker_id', type=str, required=True)

worker_parser = reqparse.RequestParser()
worker_parser.add_argument('turk_id', type=str, required=True)

class WorkerApi(Resource):
    def get(self):
        args = worker_get_parser.parse_args()
        worker_id = args['worker_id']
        worker = Worker.objects.get_or_404(id=worker_id)
        return json.loads(worker.to_json())

    def put(self):
        args = worker_parser.parse_args()
        
        turk_id = args['turk_id']

        workerDocument = Worker(turk_id)
        workerDocument.save()

        return {'worker_id' : str(workerDocument.id)}
