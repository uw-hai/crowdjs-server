import traceback
import unittest
import schema
from app import app, db, user_datastore
from redis_util import redis_get_worker_assignments_var, redis_get_task_queue_var
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

def clear_redis():
    """
    Delete all keys from the Redis database.
    """
    app.redis.flushdb()

class AppTestCase(unittest.TestCase):
    def setUp(self):
        clear_db()
        clear_redis()
        self.app = app.test_client()
        
        with app.app_context():
            self.test_requester = register_user(email='dan@crowdlab.com',
                                                password='chrisisawesome')
            self.test_requester_api_key = self.test_requester.get_auth_token()

        #XXX make a garbage request to avoid any app.before_first_request surprises
        self.app.get('/')

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


        #Add one task
        test_task_name = uuid.uuid1().hex
        test_task = dict(task_name = test_task_name,
                         task_description = 'test task with 2 questions',
                         requester_id = str(self.test_requester.id),
                         questions = [test_question1, test_question2],
                         total_task_budget=3)
        
        rv = self.app.put('/tasks',
                          content_type='application/json',
                          data=json.dumps(test_task))
        self.assertEqual(401, rv.status_code)

        rv = self.app.put('/tasks', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_task))
        self.assertEqual(200, rv.status_code)
        task_id = json.loads(rv.data)['task_id']

        #check that task questions were inserted and
        #that each ID returned corresponds to the correct question
        q_ids = json.loads(rv.data)['question_ids']
        self.assertEqual(2, len(q_ids))
        q_obj1 = schema.question.Question.objects.get(id = q_ids[0])
        q_obj2 = schema.question.Question.objects.get(id = q_ids[1])
        self.assertEqual(test_question1['question_name'], q_obj1.name)
        self.assertEqual(test_question2['question_name'], q_obj2.name)


        self.assertEqual(200, rv.status_code)
        self.assertEqual(1, len(schema.task.Task.objects))

        db_first_task = schema.task.Task.objects.first()

        self.assertEqual(str(db_first_task.id), task_id)
        rv = self.app.get('/tasks/%s' % task_id)
        get_task = json.loads(rv.data)
        self.assertEqual(200, rv.status_code)
        self.assertEqual(task_id, get_task['_id']['$oid'])

        #Add a second task
        test_task2 = dict(task_name = uuid.uuid1().hex,
                          task_description = 'test task 2',
                          requester_id = str(self.test_requester.id))
        rv2 = self.app.put('/tasks', content_type='application/json',
                           data=json.dumps(test_task2))
        self.assertEqual(401, rv2.status_code)
        
        rv2 = self.app.put('/tasks', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_task2))
        self.assertEqual(200, rv2.status_code)

        task_id2 = json.loads(rv2.data)['task_id']
        self.assertEqual(200, rv.status_code)

        #Get these tasks by requester
        rv = self.app.get('/tasks', content_type = 'application/json')
        self.assertEqual(401, rv.status_code)

        rv = self.app.get('/tasks', content_type = 'application/json',
                          headers={'Authentication-Token':
                                   'blah'})
        self.assertEqual(401, rv.status_code)

        get_request = dict(requester_id = str(self.test_requester.id))
        rv = self.app.get('/tasks', content_type = 'application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(get_request))
        self.assertEqual(200, rv.status_code)
        tasks = json.loads(rv.data)
        task_ids = [x['_id']['$oid'] for x in tasks]
        self.assertEqual(2, len(tasks))
        self.assertIn(task_id, task_ids)
        self.assertIn(task_id2, task_ids)
        self.assertNotEqual(task_ids[0], task_ids[1])

            
        # TEST add question to existing task
        test_question3_name = uuid.uuid1().hex
        test_question3_description = "question 3 description here"
        test_question3 = dict(question_name=test_question3_name,
                              question_description=test_question3_description,
                              question_data='84',
                              answers_per_question = 10,
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

        # Check list of all questions using questionlistapi
        rv = self.app.get('/questions')
        self.assertEqual(401, rv.status_code)

        questions_get_request = dict(requester_id = str(self.test_requester.id))
        rv = self.app.get('/questions', content_type = 'application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(questions_get_request))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(3, len(ret_data))


        questions_get_request = dict(requester_id = str(self.test_requester.id),
                                     task_id = task_id)
        rv = self.app.get('/questions', content_type = 'application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(questions_get_request))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(2, len(ret_data))
        
        questions_get_request = dict(requester_id = str(self.test_requester.id),
                                     task_id = task_id2)
        rv = self.app.get('/questions', content_type = 'application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(questions_get_request))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(1, len(ret_data))

        
        ###
        # There maybe should not be an API for adding/modifying workers
        ###
        # Add worker
        #test_turk_id = "xxxTEST_TURK_ID"
        #test_worker = dict(turk_id = test_turk_id)
        #rv = self.app.put('/workers', content_type='application/json', data=json.dumps(test_worker))
        #get_worker = json.loads(rv.data)
        #test_worker_id = get_worker['worker_id']

        # Check that worker was successfully added
        #rv = self.app.get('/workers/%s' % test_worker_id)
        #get_worker = json.loads(rv.data)
        #saved_worker_id = get_worker['turk_id']
        #self.assertEqual(test_turk_id, saved_worker_id)

        test_worker_id = 'MTURK123XYZ'
        test_worker_id_2 = 'MTURK56789'
        test_worker_id_3 = 'MTURK31415'

        test_worker_source = 'mturk'


        ####################################################################
        # Test Assignment
        ####################################################################
        wt_pair = dict(worker_id=test_worker_id,
                       worker_source=test_worker_source,
                       task_id=task_id,
                       requester_id=str(self.test_requester.id),
                       strategy='min_answers')
        
        wt_pair_worker2 = dict(worker_id=test_worker_id_2,
                               worker_source=test_worker_source,
                               task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               strategy='min_answers')

        wt_pair_worker3 = dict(worker_id=test_worker_id_3,
                               worker_source=test_worker_source,
                               task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               strategy='min_answers')

        


        wt_pair_preview = dict(worker_id=test_worker_id,
                               worker_source=test_worker_source,
                               task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               strategy='min_answers',
                               preview=True)

        wt_pair_preview_random = dict(worker_id=test_worker_id,
                                      worker_source=test_worker_source,
                                      task_id=task_id,
                                      requester_id=str(self.test_requester.id),
                                      strategy='random',
                                      preview=True)

        
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        assign1 = json.loads(rv.data)['question_name']

        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        assign2 = json.loads(rv.data)['question_name']

        #The assignment should be the same, and there should only be one
        #answer awaiting completion in the databse
        self.assertEqual(assign1, assign2)
        self.assertEqual(len(schema.answer.Answer.objects), 1)

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))

        #try assigning task 1 again to worker 2 (Question 2)
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_worker2))
        self.assertEqual(200, rv.status_code)
        assign3 = json.loads(rv.data)['question_name']
        self.assertEqual(len(schema.answer.Answer.objects), 2)

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(0, len(task_queue))

        
        #try assigning again, but shouldn't work because of
        #exceeded budget. By default each assignment has budget 1.
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_worker3))

        self.assertEqual(200, rv.status_code)
        self.assertIn('error', json.loads(rv.data))


        print "Setting the budget to be 2 answers per question"
        set_budget_data = dict(task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               answers_per_question=2)

        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           data=json.dumps(set_budget_data))
        self.assertEqual(401, rv.status_code)

        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    self.test_requester_api_key},
                           data=json.dumps(set_budget_data))
        self.assertEqual(200, rv.status_code)

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(2, len(task_queue))

        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_worker3))
        self.assertEqual(200, rv.status_code)
        assign4 = json.loads(rv.data)['question_name']

        
        #Three assignments have been made at this point. That means
        #there should be 3 answers awaiting completion.
        answer_get_query = dict(requester_id=str(self.test_requester.id),
                                task_id = task_id)
        answer_get_query_no_task_id = dict(
            requester_id=str(self.test_requester.id))
        answer_get_query_wrong_task_id = dict(
            requester_id=str(self.test_requester.id),
            task_id=task_id2[::-1])
        
        rv = self.app.get('/answers', content_type='application/json')
        self.assertEqual(401, rv.status_code)

        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(3, len(answers))
        for answer in answers:
            self.assertEqual(answer['status'], 'Assigned')
            self.assertNotIn('complete_time', answer)
            self.assertNotIn('value', answer)

        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_wrong_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual("Sorry, your api token is not correct",
                         answers)
            
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(3, len(answers))
        for answer in answers:
            self.assertEqual(answer['status'], 'Assigned')
            self.assertNotIn('complete_time', answer)
            self.assertNotIn('value', answer)

        #Test asking for a preview
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_preview))
        self.assertEqual(200, rv.status_code)
        self.assertIn('question_name', json.loads(rv.data))
 
        #Test asking for a preview using the random strategy
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_preview_random))
        self.assertEqual(200, rv.status_code)
        self.assertIn('question_name', json.loads(rv.data))
        
        #There should still be only 3 answers
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(3, len(answers))

        # Test adding answers
        print "Adding answer to Assign1"
        test_answer = dict(question_name=assign1,
                           requester_id = str(self.test_requester.id),
                           task_id = task_id,
                           worker_id=test_worker_id,
                           worker_source=test_worker_source,
                           value="test answer value")        

        rv = self.app.put('/answers', content_type='application/json',
                          data=json.dumps(test_answer))
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        self.assertEqual(get_answer['value'], "test answer value")

        #There should still be 3 answers
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(3, len(answers))

        # check that answer value is correct and was added to the question
        # for a single Answer
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        num_answers_with_no_value = 0
        num_answers_with_test_value = 0
        answer_with_test_value = None
        for answer in ret_data:
            if 'value' not in answer:
                num_answers_with_no_value += 1
            elif answer['value'] == test_answer['value']:
                num_answers_with_test_value += 1
                answer_with_test_value = answer
                
        self.assertEqual(num_answers_with_no_value, 2)
        self.assertEqual(num_answers_with_test_value, 1)

        rv = self.app.get('/questions/%s' %
                          answer_with_test_value['question']['$oid'])
        self.assertEqual(200, rv.status_code)
        question_name = json.loads(rv.data)

        self.assertEqual(question_name['name'], assign1)


        #Test adding an answer to a question that wasn't assigned.
        print "Adding answer for task 2, question3, qorker 1"
        test_answer = dict(question_name=test_question3_name,
                           task_id=task_id2,
                           requester_id=str(self.test_requester.id),
                           worker_id=test_worker_id,
                           worker_source=test_worker_source,
                           value="31415")
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_answer))
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        self.assertEqual(get_answer['value'], "31415")

        #There should now be 4 answers
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(4, len(answers))

        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(3, len(answers))

        # check that answer value is correct and was added to the question
        # for a single Answer
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        num_answers_with_no_value = 0
        num_answers_with_test_value = 0
        num_answers_with_other_values = 0
        answer_with_test_value = None
        for answer in ret_data:
            if 'value' not in answer:
                num_answers_with_no_value += 1
            elif answer['value'] == "31415":
                num_answers_with_test_value += 1
                answer_with_test_value = answer
            else:
                num_answers_with_other_values += 1
                
        self.assertEqual(num_answers_with_no_value, 2)
        self.assertEqual(num_answers_with_test_value, 1)
        self.assertEqual(num_answers_with_other_values, 1)
        
        rv = self.app.get('/questions/%s' %
                          answer_with_test_value['question']['$oid'])
        self.assertEqual(200, rv.status_code)
        question_name = json.loads(rv.data)

        self.assertEqual(question_name['name'], test_question3_name)


        # Test adding another answer for which we are expecting one
        print "Adding answer to Assign3"
        test_answer = dict(question_name=assign3,
                           requester_id = str(self.test_requester.id),
                           task_id = task_id,
                           worker_id=test_worker_id_2,
                           worker_source=test_worker_source,
                           value="assign2value")
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_answer))
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        self.assertEqual(get_answer['value'], "assign2value")
            
        #There should still be 4 answers
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(4, len(answers))


        # check that answer value is correct and was added to the question
        # for a single Answer
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        num_answers_with_no_value = 0
        num_answers_with_test_value = 0
        num_answers_with_other_values = 0
        answer_with_test_value = None
        for answer in ret_data:
            if 'value' not in answer:
                num_answers_with_no_value += 1
            elif answer['value'] == test_answer['value']:
                num_answers_with_test_value += 1
                answer_with_test_value = answer
            else:
                num_answers_with_other_values += 1

                
        self.assertEqual(num_answers_with_no_value, 1)
        self.assertEqual(num_answers_with_test_value, 1)
        self.assertEqual(num_answers_with_other_values, 2)
        
        rv = self.app.get('/questions/%s' %
                          answer_with_test_value['question']['$oid'])
        self.assertEqual(200, rv.status_code)
        question_name = json.loads(rv.data)

        self.assertEqual(question_name['name'], assign3)

        #Test that there are currently two questions on the redis queue
        #for task 1
        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))


        # Test adding two answers -one which we are expecting, and
        #one which we will not be expecting after adding the first
        print "Adding answer for assign4"
        test_answer = dict(question_name=assign4,
                           requester_id = str(self.test_requester.id),
                           task_id = task_id,
                           worker_id=test_worker_id_3,
                           worker_source=test_worker_source,
                           value="assign3value1")
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_answer))
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        self.assertEqual(get_answer['value'], "assign3value1")


        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))

        print "Adding a second unexpected answer for assign4"
        test_answer = dict(question_name=assign4,
                           requester_id = str(self.test_requester.id),
                           task_id = task_id,
                           worker_id=test_worker_id_3,
                           worker_source=test_worker_source,
                           value="assign3value2")
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(test_answer))
        self.assertEqual(200, rv.status_code)
        get_answer = json.loads(rv.data)
        self.assertEqual(get_answer['value'], "assign3value2")

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))

        
        #There should now be 5 answers
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        self.assertEqual(5, len(answers))


        # check that answer values are correct and were added to the
        # appropriate questions
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        num_answers_with_no_value = 0
        num_answers_with_test_value = 0
        num_answers_with_other_values = 0
        answer_with_test_value = None
        for answer in ret_data:
            if 'value' not in answer:
                num_answers_with_no_value += 1
            elif answer['value'] == test_answer['value']:
                num_answers_with_test_value += 1
                answer_with_test_value = answer
            else:
                num_answers_with_other_values += 1

                
        self.assertEqual(num_answers_with_no_value, 0)
        self.assertEqual(num_answers_with_test_value, 1)
        self.assertEqual(num_answers_with_other_values, 4)
        
        rv = self.app.get('/questions/%s' %
                          answer_with_test_value['question']['$oid'])
        self.assertEqual(200, rv.status_code)
        question_name = json.loads(rv.data)

        self.assertEqual(question_name['name'], assign4)

        #Test that all answers have a completed time greater than assigned time
        rv = self.app.get('/answers', content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(answer_get_query_no_task_id))
        self.assertEqual(200, rv.status_code)
        answers = json.loads(rv.data)
        answers_with_assign_times = 0
        for answer in answers:
            self.assertIn('complete_time', answer)
            if 'assign_time' in answer:
                answers_with_assign_times += 1
                self.assertLess(answer['assign_time'], answer['complete_time'])

        self.assertEqual(answers_with_assign_times, 3)

        #Test that we can no longer make assignments because of task budget.
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        self.assertIn('error', json.loads(rv.data))

        set_budget_data = dict(task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               total_task_budget=6)
        
        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    self.test_requester_api_key},
                           data=json.dumps(set_budget_data))
        self.assertEqual(200, rv.status_code)

        
        #Test that we can make 1 more assignment.
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair))
        self.assertEqual(200, rv.status_code)
        self.assertNotEqual(None, json.loads(rv.data))

        #and the next assignment will not work because of budget
        #only 2 answers per question
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   self.test_requester_api_key},
                          data=json.dumps(wt_pair_worker2))
        self.assertEqual(200, rv.status_code)
        self.assertIn('error', json.loads(rv.data))

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
        new_requester = dict(email='seth@crowdlab.com', password='newreqpassword')
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(new_requester))
        self.assertEqual(200, rv.status_code)

        rv = self.app.get('/requesters')
        self.assertEqual(200, rv.status_code)
        ret_data = json.loads(rv.data)
        self.assertEqual(2, len(ret_data))

        #############
        # Test clearing redis cache
        #############

        task_queue_var = redis_get_task_queue_var(task_id2,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(0, len(task_queue))


        print "Setting the budget to be 3 answers per question"
        set_budget_data = dict(task_id=task_id,
                               requester_id=str(self.test_requester.id),
                               answers_per_question=3)

        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    self.test_requester_api_key},
                           data=json.dumps(set_budget_data))
        self.assertEqual(200, rv.status_code)

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(2, len(task_queue))

        total_workers_assignments = 0
        for worker in schema.worker.Worker.objects():
            total_workers_assignments += app.redis.scard(
                redis_get_worker_assignments_var(task_id2, worker.id))
        self.assertEqual(0, total_workers_assignments)

        total_workers_assignments = 0
        for worker in schema.worker.Worker.objects():
            total_workers_assignments += app.redis.scard(
                redis_get_worker_assignments_var(task_id, worker.id))
        self.assertEqual(4, total_workers_assignments)
            

        del_request = dict(requester_id=str(self.test_requester.id),
                           task_id = task_id)
        rv = self.app.post('tasks/clearredis',
                      content_type='application/json',
                      headers={'Authentication-Token':
                               self.test_requester_api_key},
                      data=json.dumps(del_request))
        self.assertEqual(200, rv.status_code)
        print rv.data

        task_queue_var = redis_get_task_queue_var(task_id,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(0, len(task_queue))
        
        task_queue_var = redis_get_task_queue_var(task_id2,
                                                  'min_answers')
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        self.assertEqual(1, len(task_queue))

        total_workers_assignments = 0
        for worker in schema.worker.Worker.objects():
            total_workers_assignments += app.redis.scard(redis_get_worker_assignments_var(task_id2, worker.id))
        self.assertEqual(0, total_workers_assignments)

        total_workers_assignments = 0
        for worker in schema.worker.Worker.objects():
            total_workers_assignments += app.redis.scard(redis_get_worker_assignments_var(task_id, worker.id))
        self.assertEqual(0, total_workers_assignments)
            
        ##########
        # TEST DELETING TASKS
        ##########
        self.assertEqual(2, len(schema.task.Task.objects()))
        self.assertEqual(3, len(schema.question.Question.objects()))
        self.assertEqual(6, len(schema.answer.Answer.objects()))

        del_request = dict(requester_id=str(self.test_requester.id),
                           task_id = task_id2)
        rv = self.app.post('/tasks/delete',
                           content_type='application/json',
                           data=json.dumps(del_request))
        self.assertEqual(401, rv.status_code)

        rv = self.app.post('/tasks/delete',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    self.test_requester_api_key},
                           data=json.dumps(del_request))
        self.assertEqual(200, rv.status_code)

        self.assertEqual(0, len(schema.task.Task.objects(id=task_id2)))
        self.assertEqual(0, len(schema.question.Question.objects(id=task_id2)))
        self.assertEqual(0, len(schema.answer.Answer.objects(id=task_id2)))

        self.assertEqual(1, len(schema.task.Task.objects()))
        self.assertEqual(2, len(schema.question.Question.objects()))
        self.assertEqual(5, len(schema.answer.Answer.objects()))

        del_request_no_task_id = dict(requester_id=str(self.test_requester.id))

        rv = self.app.post('/tasks/delete',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    self.test_requester_api_key},
                           data=json.dumps(del_request_no_task_id))
        self.assertEqual(200, rv.status_code)

        self.assertEqual(0, len(schema.task.Task.objects()))
        self.assertEqual(0, len(schema.question.Question.objects()))
        self.assertEqual(0, len(schema.answer.Answer.objects()))


        

        
    def test_populate_db(self):
        # Start with clean DB for sanity
        clear_db()

        print "POPULATING DB..."

        #XXX systematic way to save IDs
        requester1 = dict(email = "seth+1@crowdlab.com", password="badpassword")
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(requester1))
        self.assertEqual(200, rv.status_code)
        requester1_id = json.loads(rv.data)['requester_id']
        with app.app_context():
            requester1_token = user_datastore.get_user(
                requester1_id).get_auth_token()

        requester2 = dict(email = "seth+2@crowdlab.com",
                          password="sethsbadpassword")
        rv = self.app.put('/requesters', content_type='application/json', data=json.dumps(requester2))
        self.assertEqual(200, rv.status_code)
        requester2_id = json.loads(rv.data)['requester_id']
        with app.app_context():
            requester2_token = user_datastore.get_user(
                requester2_id).get_auth_token()

        # questions without task + requester (MUST BE ADDED AS PART OF A TASK)
        question1_name = 'q1 name'
        question2_name = 'q2 name'
        question1 = dict(question_name = question1_name, question_description = "q1 desc", question_data = "data11111",
                        valid_answers = ["cat", "dog"])
        question2 = dict(question_name = question2_name, question_description = "q2 desc", question_data = "data22222")

        #Add tasks
        task1 = dict(task_name = "test task w/preloaded Qs", task_description = "description here",
                        requester_id = requester1_id, questions = [question1, question2])
        task2 = dict(task_name = "test task where questions loaded later", task_description = "t2 desc",
                        requester_id = requester2_id)


        rv = self.app.put('/tasks', content_type='application/json',
                          headers={'Authentication-Token': requester1_token},
                          data=json.dumps(task1))
        self.assertEqual(200, rv.status_code)
        
        task1_id = json.loads(rv.data)['task_id']
        q_ids = json.loads(rv.data)['question_ids']
        question1_id = q_ids[0]
        question2_id = q_ids[1]
        
        rv = self.app.put('/tasks', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(task2))
        self.assertEqual(200, rv.status_code)

        
        task2_id = json.loads(rv.data)['task_id']

        # add questions 3-5 to task2
        question3_name = 'q3 name'
        question4_name = 'q4 name'
        question5_name = 'q5 name'
        
        question3 = dict(question_name = question3_name, question_description = "q3 desc", question_data = "data3333333333",
                                task_id = task2_id, requester_id = requester2_id)
        question4 = dict(question_name = question4_name, question_description = "q4 desc", question_data = "data4444444444444",
                                task_id = task2_id, requester_id = requester2_id)
        question5 = dict(question_name = question5_name, question_description = "q5 desc", question_data = "data55555",
                                task_id = task2_id, requester_id = requester2_id, valid_answers = ["animal", "vegetable", "mineral"])

        rv = self.app.put('/questions', content_type='application/json',
                          data=json.dumps(question3))
        self.assertEqual(200, rv.status_code)
        question3_id = json.loads(rv.data)['question_id']
        
        rv = self.app.put('/questions', content_type='application/json', data=json.dumps(question4))
        self.assertEqual(200, rv.status_code)
        question4_id = json.loads(rv.data)['question_id']
        
        
        rv = self.app.put('/questions', content_type='application/json', data=json.dumps(question5))
        self.assertEqual(200, rv.status_code)
        question5_id = json.loads(rv.data)['question_id']


        # Test question assignment algorithms
        # First set the budget high enough
        set_budget_data = dict(task_id=task1_id,
                               requester_id=requester1_id,
                               answers_per_question=10)
        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    requester1_token},
                           data=json.dumps(set_budget_data))
        self.assertEqual(200, rv.status_code)
        set_budget_data = dict(task_id=task2_id,
                               requester_id=requester2_id,
                               answers_per_question=10)
        rv = self.app.post('/tasks/set_budget',
                           content_type='application/json',
                           headers={'Authentication-Token':
                                    requester2_token},
                           data=json.dumps(set_budget_data))
        self.assertEqual(200, rv.status_code)

        # Add workers
        ###
        # DONT NEED TO ADD WORKERS
        ###
        worker_platform = 'mturk'        
        worker1 = dict(platform_id = "turk1", platform_name=worker_platform)
        worker2 = dict(platform_id = "turk2", platform_name=worker_platform)
        worker3 = dict(platform_id = "turk3", platform_name=worker_platform)
        worker4 = dict(platform_id = "turk4", platform_name=worker_platform)
        worker5 = dict(platform_id = "turk5", platform_name=worker_platform)


        #rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker1))
        #self.assertEqual(200, rv.status_code)
        #worker1_id = json.loads(rv.data)['worker_id']

        #rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker2))
        #self.assertEqual(200, rv.status_code)
        #worker2_id = json.loads(rv.data)['worker_id']

        #rv = self.app.put('/workers', content_type='application/json', data=json.dumps(worker3))
        #self.assertEqual(200, rv.status_code)
        #worker3_id = json.loads(rv.data)['worker_id']
        
        
        # Add answers

        answer1 = dict(value = "dog", question_name = question1_name,
                       worker_id = worker1['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester1_id,
                       task_id = task1_id)
        answer2 = dict(value = "sheep", question_name = question2_name,
                       worker_id = worker1['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester1_id,
                       task_id = task1_id)
        answer3 = dict(value = "cat", question_name = question1_name,
                       worker_id = worker2['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester1_id,
                       task_id = task1_id)
        answer4 = dict(value = "husky", question_name = question5_name,
                       worker_id = worker2['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester2_id,
                       task_id = task2_id)
        answer5 = dict(value = "cat", question_name = question1_name,
                       worker_id = worker3['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester1_id,
                       task_id = task1_id)
        answer6 = dict(value = "apple", question_name = question3_name,
                       worker_id = worker3['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester2_id,
                       task_id = task2_id)
        answer7 = dict(value = "biscuit", question_name = question4_name,
                       worker_id = worker3['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester2_id,
                       task_id = task2_id)
        answer8 = dict(value = "husky dog", question_name = question5_name,
                       worker_id = worker3['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester2_id,
                       task_id = task2_id)

        # XXX added another answer to question 3 by worker 1
        answer9 = dict(value = "good answer", question_name = question3_name,
                       worker_id = worker1['platform_id'],
                       worker_source=worker_platform,
                       is_alive = True,
                       requester_id = requester2_id,
                       task_id = task2_id)

        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester1_token},
                          data=json.dumps(answer1))
        self.assertEqual(200, rv.status_code)
        answer1_value = json.loads(rv.data)['value']
        self.assertEqual("dog", answer1_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester1_token},
                          data=json.dumps(answer2))
        self.assertEqual(200, rv.status_code)
        answer2_value = json.loads(rv.data)['value']
        self.assertEqual("sheep", answer2_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester1_token},
                          data=json.dumps(answer3))        
        self.assertEqual(200, rv.status_code)
        answer3_value = json.loads(rv.data)['value']        
        self.assertEqual("cat", answer3_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(answer4))
        self.assertEqual(200, rv.status_code)
        answer4_value = json.loads(rv.data)['value']
        self.assertEqual("husky", answer4_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester1_token},
                          data=json.dumps(answer5))
        self.assertEqual(200, rv.status_code)
        answer5_value = json.loads(rv.data)['value']
        self.assertEqual("cat", answer5_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(answer6))
        self.assertEqual(200, rv.status_code)
        answer6_value = json.loads(rv.data)['value']
        self.assertEqual("apple", answer6_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(answer7))
        self.assertEqual(200, rv.status_code)
        answer7_value = json.loads(rv.data)['value']
        self.assertEqual("biscuit", answer7_value)
        
        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(answer8))
        self.assertEqual(200, rv.status_code)
        answer8_value = json.loads(rv.data)['value']
        self.assertEqual("husky dog", answer8_value)


        rv = self.app.put('/answers', content_type='application/json',
                          headers={'Authentication-Token': requester2_token},
                          data=json.dumps(answer9))
        self.assertEqual(200, rv.status_code)
        answer9_value = json.loads(rv.data)['value']
        self.assertEqual("good answer", answer9_value)


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


        
        # Task 1's least answered question is question 2
        assign1 = dict(worker_id = worker4['platform_id'],
                       worker_source = worker_platform,
                       task_id = task1_id,
                       requester_id = requester1_id,
                       strategy = 'min_answers')
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   requester1_token}, 
                          data=json.dumps(assign1))
        self.assertEqual(200, rv.status_code)
        assign1_name = json.loads(rv.data)['question_name']
        self.assertEqual(question2['question_name'], assign1_name)

        # Task 2's least answered question is question 4
        assign2 = dict(worker_id = worker5['platform_id'],
                       worker_source = worker_platform,
                       task_id = task2_id,
                       requester_id = requester2_id,
                       strategy = 'min_answers')
        
        rv = self.app.get('/assign_next_question',
                          content_type='application/json',
                          headers={'Authentication-Token':
                                   requester2_token}, 
                          data=json.dumps(assign2))
        self.assertEqual(200, rv.status_code)
        assign2_name = json.loads(rv.data)['question_name']
        self.assertEqual(question4['question_name'], assign2_name)

        # Test answer aggregation algorithms

        # Majority vote answer to question 1 is "cat"
        agg1 = dict(question_id = question1_id,
                    strategy='majority_vote')
        rv = self.app.get('/aggregated_answer',
                          content_type='application/json',
                          data=json.dumps(agg1))
        self.assertEqual(200, rv.status_code)
        agg1_answer = json.loads(rv.data)['aggregated_answer']
        self.assertEqual("cat", agg1_answer)

        # Check that inference result was saved in DB
        q1 = schema.question.Question.objects.get_or_404(
            name=question1['question_name'])
        saved_result = q1.inference_results[agg1['strategy']]
        self.assertEqual(agg1_answer, saved_result)

        # Test basic task-level aggregation
        # Using task1, requester1 for convenience

        #start job
        task1_agg1_data = dict(requester_id=requester1_id, strategy='majority_vote')
        task1_agg1_url = '/tasks/%s/aggregate' % task1_id
        rv = self.app.put(task1_agg1_url,
                    content_type='application/json',
                    headers={'Authentication-Token':
                                   requester1_token}, 
                    data=json.dumps(task1_agg1_data))
        self.assertEqual(200, rv.status_code)
        ret = json.loads(rv.data)
        job_id = ret['_id']['$oid']
        print 'Job PUT return data=', ret

        #check job status
        task1_agg1_get_data = dict(requester_id=requester1_id)
        rv = self.app.get(task1_agg1_url + '/' + job_id,
                content_type='application/json',
                headers={'Authentication-Token':
                                requester1_token},
                data=json.dumps(task1_agg1_get_data))
        ret = json.loads(rv.data)
        print 'Job GET return data=', ret

        print("Done populating DB.")

        
    def tearDown(self):
        clear_db()
        clear_redis()

if __name__ == '__main__':
    unittest.main()
