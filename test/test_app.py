import traceback
import unittest
import schema
from app import app, db, user_datastore
from flask.ext.security.registerable import register_user
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
        
        with app.app_context():
            self.test_requester = register_user(email='dan@crowdlab.com',
                                                password='chrisisawesome')

    def test_add_test_questions_and_task(self):
        requesters = schema.requester.Requester.objects(
            email='dan@crowdlab.com')
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
        
        rv = self.app.put('/tasks',
                          content_type='application/json',
                          data=json.dumps(test_task))
        task_id = json.loads(rv.data)['task_id']

        self.assertEqual(200, rv.status_code)
        self.assertEqual(1, len(schema.task.Task.objects))

        db_first_task = schema.task.Task.objects.first()

        self.assertEqual(str(db_first_task.id), task_id)
        rv = self.app.get('/tasks/%s' % task_id)
        get_task = json.loads(rv.data)
        self.assertEqual(200, rv.status_code)
        self.assertEqual(task_id, get_task['_id']['$oid'])

        # TEST add question to existing task
        test_task2 = dict(task_name = uuid.uuid1().hex, task_description = 'test task 2', requester_id = str(self.test_requester.id))
        rv2 = self.app.put('/tasks', content_type='application/json',data=json.dumps(test_task2))
        task_id2 = json.loads(rv2.data)['task_id']
        self.assertEqual(200, rv.status_code)

        test_question3_name = uuid.uuid1().hex
        test_question3_description = "question 3 description here"
        test_question3 = dict(question_name=test_question3_name,
                              question_description=test_question3_description,
                              question_data='84',
                              task_id=task_id2,
                              requester_id = str(self.test_requester.id))

        rvq = self.app.put('/questions', content_type='application/json', data=json.dumps(test_question3))
        test_question3_id = json.loads(rvq.data)['question_id']

        # Check that our specific question was added to the task
        rv = self.app.get('/tasks/%s' % task_id2)
        self.assertEqual(200, rv.status_code)
        get_task = json.loads(rv.data)
        self.assertEqual(1, len(get_task['questions']))
        print get_task['questions'], type(get_task['questions'])
        saved_q3_id = get_task['questions'][0]['_id']['$oid']
        self.assertEqual(test_question3_id, saved_q3_id)

        # Check integrity of question
        rv = self.app.get('/questions/%s' % test_question3_id)
        self.assertEqual(200, rv.status_code)
        get_question = json.loads(rv.data)
        self.assertEqual(test_question3_name, get_question['name'])
        self.assertEqual(test_question3_description, get_question['description'])

        # Check list of all questions
        rv = self.app.get('/questions')
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(3, len(ret_data))

        # Add worker
        test_turk_id = "xxxTEST_TURK_ID"
        test_worker = dict(turk_id = test_turk_id)
        rv = self.app.put('/workers', content_type='application/json', data=json.dumps(test_worker))
        get_worker = json.loads(rv.data)
        test_worker_id = get_worker['worker_id']

        # Check that worker was successfully added
        rv = self.app.get('/workers/%s' % test_worker_id)
        get_worker = json.loads(rv.data)
        saved_worker_id = get_worker['turk_id']
        self.assertEqual(test_turk_id, saved_worker_id)

        # Test adding an answer
        test_answer = dict(question_id=test_question3_id, worker_id=test_worker_id, value="test answer value")
        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(test_answer))
        #expected_add_answer_rv = "Answer inserted"
        expected_add_answer_rv = "test answer value"
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        test_answer_id = get_answer['answer_id']
        self.assertEqual(get_answer['value'], expected_add_answer_rv)

        # check that answer value is correct and was added to the question
        rv = self.app.get('/answers/%s' % test_answer_id)
        ret_data = json.loads(rv.data)
        self.assertEqual(200, rv.status_code)
        self.assertEqual(ret_data['answer_id'], test_answer_id)
        self.assertEqual(ret_data['value'], test_answer['value'])
        self.assertEqual(ret_data['question_id'], test_answer['question_id'])
        self.assertEqual(ret_data['worker_id'], test_answer['worker_id'])

        # test /requesters functionality
        rv = self.app.get('/requesters')
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(1, len(ret_data))
        self.assertEqual(str(self.test_requester.id), ret_data[0]['_id']['$oid'])

        # test getting data of specific requester
        rv = self.app.get('/requesters/%s' % self.test_requester.id)
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual("dan@crowdlab.com", ret_data['email'])

        # test retrieving tasks requested by specific requester
        rv = self.app.get('/requesters/%s/tasks' % self.test_requester.id)
        ret_data = json.loads(rv.data)
        self.assertEqual(2, len(ret_data))

        # test adding new requester
        #TODO check integrity of requester data?
        new_requester = dict(email='sethv1@cs.uw.edu', password='newreqpassword')
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(new_requester))
        self.assertEqual(200, rv.status_code)

        rv = self.app.get('/requesters')
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(2, len(ret_data))


        rv = self.app.get('/workers')
        print rv.data

        rv = self.app.get('/workers/%s' % test_worker_id)
        print rv.data

        rv = self.app.get('/workers/%s/answers' % test_worker_id)
        print rv.data

        rv = self.app.get('/tasks/%s/questions' % task_id)
        print rv.data

        rv = self.app.get('/questions/%s/answers' % test_question3_id)
        print rv.data

        # TODO more rigorous testing of question assignment,
        # including different stategies and checking of
        # results based on what should be in the DB.

        wt_pair = dict(worker_id=test_worker_id, task_id=task_id)
        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        print rv.data
        assign1 = json.loads(rv.data)['question_id']

        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        print rv.data
        assign2 = json.loads(rv.data)['question_id']

        # CHECK HERE WITH DIFFERENT ASSIGNMENT STRATEGIES

        rv = self.app.get('/assign_next_question?strategy=min_answers', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        print rv.data
        assign3 = json.loads(rv.data)['question_id']
        
    def tearDown(self):
        clear_db()

if __name__ == '__main__':
    unittest.main()
