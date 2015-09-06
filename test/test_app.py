import unittest
import schema
from app import app, db, user_datastore
import uuid
import json

def clear_db():
    schema.answer.Answer.objects().delete()
    schema.question.Question.objects().delete()
    schema.requester.Requester.objects().delete()
    schema.role.Role.objects().delete()
    schema.task.Task.objects().delete()
    schema.worker.Worker.objects().delete()

class AppTestCase(unittest.TestCase):
    def setUp(self):
        clear_db()
        self.app = app.test_client()
        self.test_requester = user_datastore.create_user(email='dan@weld.com', 
                                               password='chrisisawesome')

    def test_add_test_questions_and_task(self):
        requesters = schema.requester.Requester.objects(email='dan@weld.com')
        self.assertEqual(1, len(requesters))

        self.assertIsNone(schema.task.Task.objects.first())

        test_question1_name = uuid.uuid1().hex
        test_question1 = dict(question_name=test_question1_name,
                              question_description='test question 1',
                              question_data='23',
                              requester_id = str(self.test_requester.id))

        test_question2_name = uuid.uuid1().hex
        test_question2 = dict(question_name=test_question2_name,
                              question_description='test question 2',
                              question_data='42',
                              requester_id = str(self.test_requester.id))


        test_task_name = uuid.uuid1().hex
        
        test_task = dict(task_name = test_task_name,
                         task_description = 'test task with 2 questions',
                         requester_id = str(self.test_requester.id),
                         questions = [test_question1, test_question2])
        
        rv = self.app.put('/api/task', 
                          content_type='application/json',
                          data=json.dumps(test_task))
        task_id = json.loads(rv.data)['task_id']

        self.assertEqual(200, rv.status_code)
        self.assertEqual(1, len(schema.task.Task.objects))

        db_first_task = schema.task.Task.objects.first()

        self.assertEqual(str(db_first_task.id), task_id)
        rv = self.app.get('/api/task?task_id=%s' % task_id)
        get_task = json.loads(rv.data)
        self.assertEqual(200, rv.status_code)
        self.assertEqual(task_id, get_task['_id']['$oid'])
        
    def tearDown(self):
        clear_db()

if __name__ == '__main__':
    unittest.main()
