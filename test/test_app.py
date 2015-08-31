import unittest
import schema
from app import app, db

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
        r = self.app.get('/')
    def test_add_test_questions_and_task(self):
        r = self.app.get('/add_test_questions_and_task')
        requesters = schema.requester.Requester.objects(email='dan@weld.com')
        self.assertEqual(1, len(requesters))
    def tearDown(self):
        clear_db()

if __name__ == '__main__':
    unittest.main()
