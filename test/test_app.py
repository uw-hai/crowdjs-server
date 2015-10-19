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
        #print get_task['questions'], type(get_task['questions'])
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
        #print rv.data

        rv = self.app.get('/workers/%s' % test_worker_id)
        #print rv.data

        rv = self.app.get('/workers/%s/answers' % test_worker_id)
        #print rv.data

        rv = self.app.get('/tasks/%s/questions' % task_id)
        #print rv.data

        rv = self.app.get('/questions/%s/answers' % test_question3_id)
        #print rv.data

        # TODO more rigorous testing of question assignment,
        # including different stategies and checking of
        # results based on what should be in the DB.

        wt_pair = dict(worker_id=test_worker_id, task_id=task_id)
        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        #print rv.data
        assign1 = json.loads(rv.data)['question_id']

        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        #print rv.data
        assign2 = json.loads(rv.data)['question_id']

        # CHECK HERE WITH DIFFERENT ASSIGNMENT STRATEGIES

        rv = self.app.get('/assign_next_question?strategy=min_answers', content_type='application/json', data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        #print rv.data
        assign3 = json.loads(rv.data)['question_id']

    def test_populate_db(self):
        # Start with clean DB for sanity
        clear_db()

        print "POPULATING DB..."

        #XXX systematic way to save IDs
        requester1 = dict(email = "sethv1+1@cs.uw.edu", password="badpassword")
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(requester1))
        self.assertEqual(200, rv.status_code)
        requester1_id = json.loads(rv.data)['requester_id']

        requester2 = dict(email = "sethv1+2@cs.uw.edu", password="sethsbadpassword")
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(requester2))
        self.assertEqual(200, rv.status_code)
        requester2_id = json.loads(rv.data)['requester_id']

        # questions without task + requester (MUST BE ADDED AS PART OF A TASK)
        question1 = dict(question_name = "q1 name", question_description = "q1 desc", question_data = "data11111",
                        valid_answers = ["cat", "dog"])
        question2 = dict(question_name = "q2 name", question_description = "q2 desc", question_data = "data22222")

        #Add tasks
        task1 = dict(task_name = "test task w/preloaded Qs", task_description = "description here",
                        requester_id = requester1_id, questions = [question1, question2])
        task2 = dict(task_name = "test task where questions loaded later", task_description = "t2 desc",
                        requester_id = requester2_id)

        rv = self.app.put('/tasks', content_type='application/json', data=json.dumps(task1))
        self.assertEqual(200, rv.status_code)
        task1_id = json.loads(rv.data)['task_id']
        task1_q_ids = json.loads(rv.data)['question_ids']

        # XXX set question1, question2 to be their respective question IDs. How?
        # Need their IDs to be able to answer them.
        question1_id = task1_q_ids[question1['question_name']]
        question2_id = task1_q_ids[question2['question_name']]

        rv = self.app.put('/tasks', content_type='application/json', data=json.dumps(task2))
        self.assertEqual(200, rv.status_code)
        task2_id = json.loads(rv.data)['task_id']
        task2_q_ids = json.loads(rv.data)['question_ids']
        # XXX should still return empty dict of qname -> id pairs
        self.assertEqual({}, task2_q_ids)

        # add questions 3-5 to task2
        question3 = dict(question_name = "q3 name", question_description = "q3 desc", question_data = "data3333333333",
                                task_id = task2_id, requester_id = requester2_id)
        question4 = dict(question_name = "q4 name", question_description = "q4 desc", question_data = "data4444444444444",
                                task_id = task2_id, requester_id = requester2_id)
        question5 = dict(question_name = "q5 name", question_description = "q5 desc", question_data = "data55555",
                                task_id = task2_id, requester_id = requester2_id, valid_answers = ["animal", "vegetable", "mineral"])

        rv = self.app.put('/questions', content_type='application/json', data=json.dumps(question3))
        self.assertEqual(200, rv.status_code)
        question3_id = json.loads(rv.data)['question_id']

        rv = self.app.put('/questions', content_type='application/json', data=json.dumps(question4))
        self.assertEqual(200, rv.status_code)
        question4_id = json.loads(rv.data)['question_id']

        rv = self.app.put('/questions', content_type='application/json', data=json.dumps(question5))
        self.assertEqual(200, rv.status_code)
        question5_id = json.loads(rv.data)['question_id']

        # Add workers

        worker1 = dict(turk_id = "turk1")
        worker2 = dict(turk_id = "turk2")
        worker3 = dict(turk_id = "turk3")

        rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker1))
        self.assertEqual(200, rv.status_code)
        worker1_id = json.loads(rv.data)['worker_id']

        rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker2))
        self.assertEqual(200, rv.status_code)
        worker2_id = json.loads(rv.data)['worker_id']

        rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker3))
        self.assertEqual(200, rv.status_code)
        worker3_id = json.loads(rv.data)['worker_id']

        # Add answers

        answer1 = dict(value = "dog", question_id = question1_id, worker_id = worker1_id)
        answer2 = dict(value = "dog", question_id = question2_id, worker_id = worker1_id)

        answer3 = dict(value = "cat", question_id = question1_id, worker_id = worker2_id)
        answer4 = dict(value = "husky", question_id = question5_id, worker_id = worker2_id)

        answer5 = dict(value = "cat", question_id = question1_id, worker_id = worker3_id)
        answer6 = dict(value = "apple", question_id = question3_id, worker_id = worker3_id)
        answer7 = dict(value = "biscuit", question_id = question4_id, worker_id = worker3_id)
        answer8 = dict(value = "husky dog", question_id = question5_id, worker_id = worker3_id)

        # XXX added another answer to question 3 by worker 1
        answer9 = dict(value = "good answer", question_id = question3_id, worker_id = worker1_id)

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer1))
        self.assertEqual(200, rv.status_code)
        answer1_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer2))
        self.assertEqual(200, rv.status_code)
        answer2_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer3))
        self.assertEqual(200, rv.status_code)
        answer3_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer4))
        self.assertEqual(200, rv.status_code)
        answer4_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer5))
        self.assertEqual(200, rv.status_code)
        answer5_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer6))
        self.assertEqual(200, rv.status_code)
        answer6_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer7))
        self.assertEqual(200, rv.status_code)
        answer7_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer8))
        self.assertEqual(200, rv.status_code)
        answer8_id = json.loads(rv.data)['answer_id']

        rv = self.app.put('/answers', content_type='application/json', data=json.dumps(answer9))
        self.assertEqual(200, rv.status_code)
        answer9_id = json.loads(rv.data)['answer_id']

        # Done adding to DB
        # Should have:
        # 2 requesters
        # 2 tasks
        # 5 questions
        # 3 workers
        # 9 answers (q1:3, q2:1, q3:2, q4:1, q5:2)
        self.assertEqual(2, len(schema.requester.Requester.objects))
        self.assertEqual(2, len(schema.task.Task.objects))
        self.assertEqual(5, len(schema.question.Question.objects))
        self.assertEqual(3, len(schema.worker.Worker.objects))
        self.assertEqual(9, len(schema.answer.Answer.objects))

        # TODO check integrity of data (boring)

        # Test question assignment algorithms

        # Task 1's least answered question is question 2
        assign1 = dict(worker_id = worker1_id, task_id = task1_id, strategy = 'min_answers')
        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(assign1))
        self.assertEqual(200, rv.status_code)
        assign1_id = json.loads(rv.data)['question_id']
        self.assertEqual(question2_id, assign1_id)

        # Task 2's least answered question is question 4
        assign2 = dict(worker_id = worker1_id, task_id = task2_id, strategy = 'min_answers')
        rv = self.app.get('/assign_next_question', content_type='application/json', data=json.dumps(assign2))
        self.assertEqual(200, rv.status_code)
        assign2_id = json.loads(rv.data)['question_id']
        self.assertEqual(question4_id, assign2_id)

        # Test answer aggregation algorithms

        # Majority vote answer to question 1 is "cat"
        agg1 = dict(question_id = question1_id, strategy='majority_vote')
        rv = self.app.get('/aggregated_answer', content_type='application/json', data=json.dumps(agg1))
        self.assertEqual(200, rv.status_code)
        agg1_answer = json.loads(rv.data)['aggregated_answer']
        self.assertEqual("cat", agg1_answer)

        # Check that inference result was saved in DB
        q1 = schema.question.Question.objects.get_or_404(id=question1_id)
        saved_result = q1.inference_results[agg1['strategy']]
        self.assertEqual(agg1_answer, saved_result)


        print("Done populating DB.")

        
    def tearDown(self):
        clear_db()

if __name__ == '__main__':
    unittest.main()
