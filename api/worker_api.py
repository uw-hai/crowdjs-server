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
        args = worker_parser.parse_args()
        turk_id = args['turk_id']
        if turk_id:
            workers = Worker.objects(platform_id=turk_id)
            if len(workers) == 0:
                return {"exists": False}
            return {"exists": True, "worker_id": str(workers[0].id)} 
        return json.loads(Worker.objects.to_json())

    def put(self):
        """
        Create a new worker.
        """
        args = worker_parser.parse_args()
        turk_id = args['turk_id']
        workers = Worker.objects(platform_id=turk_id)
        print workers
        if len(workers) == 0:
            print "%s platformer doesnot exist, so adding" % turk_id 
            workerDocument = Worker(turk_id, "mturk")
            workerDocument.save()
            return {'new': True, 'worker_id' : str(workerDocument.id)}
        return {'new': False, 'worker_id' : str(workers[0].id)};

class WorkerAnswersApi(Resource):
    def get(self, worker_id):
        """
        Get all answers by the given worker.
        """
        answers = Answer.objects(worker=worker_id)
        return json.loads(answers.to_json())

class WorkerTaskAnswersApi(Resource):
    def get(self, task_id, platform_id):
        """
        Get all answers by the given worker, on the given task.
        """
        workers = None
        try:
            workers = Worker.objects.get(platform_id=platform_id)
        except Exception:
            print "%s platformer doesnot exist" % platform_id 
        if workers is None:
            return []
        answers = Answer.objects(worker=workers.id, task=task_id)
        return json.loads(answers.to_json())

