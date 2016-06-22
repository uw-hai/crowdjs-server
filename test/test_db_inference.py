import unittest
import uuid
from app import app, db, user_datastore
import schema
import random
import itertools
import time
from aggregation import db_inference

def randomID():
    return uuid.uuid1().hex

def clear_db():
    schema.answer.Answer.objects().delete()
    schema.question.Question.objects().delete()
    schema.requester.Requester.objects().delete()
    schema.role.Role.objects().delete()
    schema.task.Task.objects().delete()
    schema.worker.Worker.objects().delete()


class EM_DB_TestCase(unittest.TestCase):
    """Test label aggregation/estimation algorithms on DB.
    """

    def setUp(self):
        #NOTE clears DB!!!
        clear_db()

        nq = 10
        nw = 5

        #create task
        test_requester = schema.requester.Requester(email="test-email-addr",
                password="password")
        test_requester.save()

        test_task = schema.task.Task(name=randomID(),
                                description='EM Test task',
                                requester=test_requester,
                                data="",
                                total_task_budget=999999999999999)
        test_task.save()
        self.test_task = test_task

        w_ids = []
        q_ids = []

        for iw in range(nw):
            w = schema.worker.Worker(platform_id=randomID(),
                    platform_name="mturk")
            w.save()
            w_ids.append(str(w.id))

        for iq in range(nq):
            q = schema.question.Question(name=randomID(),
                    description="unittest question",
                    data="",
                    task=test_task,
                    valid_answers=['0','1'],
                    requester=test_requester)
            q.save()
            q_ids.append(str(q.id))
        print("Adding votes to DB")
        #TODO workers should probably not just answer questions randomly
        votes = {(w_id, q_id) : {'vote' : random.choice([0,1])} for (w_id, q_id) in itertools.product(w_ids, q_ids)}
        print "start time=", time.time()
        voteDocs = []
        for vote in votes:
            worker, question = vote # w_id, q_id
            value = votes[vote]['vote']
            v = schema.answer.Answer(value=str(value),
                    question=question,
                    task=test_task,
                    worker=worker,
                    status='Completed')
            voteDocs.append(v)
        print "pre insert time=", time.time()
        schema.answer.Answer.objects.insert(voteDocs)
        print "end time=", time.time()
        print("Done adding votes")

    def test_db_mv(self):
        """
        Test majority vote aggregation strategy on DB
        """
        print "Starting MV with DB..."
        print time.time()
        res = db_inference.aggregate_task_majority_vote(str(self.test_task.id))
        print time.time()
        print "MV results:", res


    def test_db_em(self):
        """
        Test expectation maximization vote aggregation and skill/difficulty inference on DB
        """
        print "Starting EM with DB..."
        print time.time()
        res = db_inference.aggregate_task_EM(str(self.test_task.id))

        print "EM results:", res
        print time.time()

        print("Reading inference results from DB...")
        for question in schema.question.Question.objects:
            print "q.id:", str(question.id), "q.name:", question.name, "q.inference_results:", question.inference_results['EM']

        for worker in schema.worker.Worker.objects:
            print "w.id:", str(worker.id), "w.platform_id:", worker.platform_id, "w.inference_results:", worker.inference_results['EM']

        print("Finished EM with DB...")
        print time.time()

if __name__ == '__main__':
    unittest.main()
