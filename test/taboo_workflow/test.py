from put_tasks import put_tasks
from delete_task import delete_task

import requests
import json
import pickle
import unittest

class TestTabooWorkflow(unittest.TestCase):
    
    def test_workflow(self):
        #crowdjs_url = 'http://floating-basin-2662.herokuapp.com'
        crowdjs_url = 'http://localhost:8000'
        email = 'dan@crowdlab.com'
        #API_KEY = 'WyI1NjhhZmU3NGRiOGY0ZjAwMDk2MTQxNjIiLCI0MjQ2MDRlZDQyYmQ4YTc0NWUxZWIxMmI1YzJmODdjMCJd.CYB1Hg.omn2MCltYW2oORhQUraq5el4O-U' #floating-basin
        API_KEY = 'WyI1NmE2YTYyMTQwZjM4ODE5NjVlNDQwZTciLCJhN2VhYTZmZDkwODM0ZjYzNWIzNmRiYjYwMWJiNmYyYyJd.CYg3uw.QXmRyAgNoJYidnqAIgQb-soyYNg' #localhost
        requester_id = '568afe74db8f4f0009614162' #floating-basin
        requester_id = '56a6a62140f3881965e440e7' #localhost

        #First delete all existing tasks
        print "DELETING ALL EXISTING TASKS"
        response = delete_task(crowdjs_url, email, API_KEY, requester_id)
        self.assertIn('success', response)
        
        #Now put in a new task
        print "INSERTING TASK"
        (response, logfile_name) = put_tasks(crowdjs_url, email,
                                             API_KEY, requester_id, 1)
        self.assertIn('task_id', response)
        task_id = response['task_id']
        
        print "OPENING LOG FILE"
        logfile = open(logfile_name, 'r')
        logfile.readline()
        logfile.readline()
        logfile.readline()
        questions = pickle.loads(logfile.read())
        
        #Now assign a question
        print "ASSIGNING A QUESTION"
        assign_url = '/assign_next_question?worker_id=worker1&worker_source=mturk&task_id=%s&requester_id=%s' % (task_id, requester_id)
        assign_url = crowdjs_url + assign_url
        r = requests.get(assign_url)
        self.assertIn('question_name', r.json())
        question_name = r.json()['question_name']


        #There should now be an answer awaiting a value in the databse
        answer_get_url = '/answers?requester_id=%s&task_id=%s' % (requester_id,
                                                                  task_id)
        answer_get_url = crowdjs_url + answer_get_url
        headers = {'Authentication-Token': API_KEY}
        r = requests.get(answer_get_url, headers=headers)

        answers = r.json()
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]['is_alive'], True)
        
        #Now do a question
        print "SUBMITTING AN ANSWER"
        answer_url = crowdjs_url + '/answers'
        answer_data = {"requester_id" : requester_id,
                       "task_id" : task_id,
                       "question_name" : question_name,
                       "worker_id" : "worker1",
                       "worker_source" : "mturk", 
                       "value" : question_name.split('\t')[0] + ' head honcho'}

        r = requests.put(answer_url, json=answer_data)
        print "Here is the response"
        print r.text

        #Now try to assign another question. This should not work
        #because the worker already answered the question
        print "ASSIGNING A QUESTION"
        assign_url = '/assign_next_question?worker_id=worker1&worker_source=mturk&task_id=%s&requester_id=%s' % (task_id, requester_id)
        assign_url = crowdjs_url + assign_url
        r = requests.get(assign_url)
        self.assertIn('error', r.json())
        
        #Now assign another question. This should also not work because
        #the budget for the question has been surpassed.
        print "ASSIGNING ANOTHER QUESTION"
        assign_url = '/assign_next_question?worker_id=worker2&worker_source=mturk&task_id=%s&requester_id=%s' % (task_id, requester_id)
        assign_url = crowdjs_url + assign_url
        r = requests.get(assign_url)
        self.assertIn('error', r.json())


        #Set the answers per question to be higher
        set_budget_url = crowdjs_url + '/tasks/set_budget'
        budget_data = {'task_id': task_id,
                       'requester_id': requester_id,
                       'answers_per_question': 3} 
        headers = {'Authentication-Token': API_KEY}
        r = requests.post(set_budget_url, headers=headers,
                          json=budget_data)
        self.assertNotIn('error', r.json())
        
        #Now assign another question. This should also not work because
        #the budget for the question has been surpassed.
        print "ASSIGNING ANOTHER QUESTION"
        assign_url = '/assign_next_question?worker_id=worker2&worker_source=mturk&task_id=%s&requester_id=%s' % (task_id, requester_id)
        assign_url = crowdjs_url + assign_url
        r = requests.get(assign_url)
        self.assertIn('question_name', r.json())
        question_name = r.json()['question_name']
        
        taboo_words = question_name.split('\t')[5]
        taboo_words = taboo_words.split(';')
        
        self.assertEqual(len(taboo_words), 2)
        self.assertNotIn('head', taboo_words)
        self.assertNotIn('honcho', taboo_words)
        self.assertIn('not', taboo_words)
        
        #Now do a question
        print "SUBMITTING ANOTHER ANSWER"        
        answer_url = crowdjs_url + '/answers'
        answer_data = {"requester_id" : requester_id,
                       "task_id" : task_id,
                       "question_name" : question_name,
                       "worker_id" : "worker1",
                       "worker_source" : "mturk", 
                       "value" : question_name.split('\t')[0] + ' head honcho'}

        r = requests.put(answer_url, json=answer_data)
        print "Here is the response"
        print r.text


        #Now assign another question to worker 1
        #This should work because there should now be a new question
        print "ASSIGNING ANOTHER QUESTION"
        assign_url = '/assign_next_question?worker_id=worker1&worker_source=mturk&task_id=%s&requester_id=%s' % (task_id, requester_id)
        assign_url = crowdjs_url + assign_url
        r = requests.get(assign_url)
        self.assertIn('question_name', r.json())
        question_name = r.json()['question_name']

        print question_name
        taboo_words = question_name.split('\t')[5]
        print taboo_words
        taboo_words = taboo_words.split(';')

        print taboo_words
        
        self.assertEqual(len(taboo_words), 4)
        self.assertIn('head', taboo_words)
        self.assertIn('honcho', taboo_words)
        self.assertIn('not', taboo_words)


        #Now check that there are two questions in total, but one has
        #a zero budget.
        question_url = '/questions?requester_id=%s' % requester_id
        question_url = crowdjs_url + question_url
        
        headers = {'Authentication-Token': API_KEY}
        r = requests.get(question_url, headers=headers)
        all_questions = r.json()
        print all_questions
        self.assertEqual(len(all_questions), 2)
        questions_with_zero_budget = 0
        questions_with_gtzero_budget = 0
        for question in all_questions:
            print question['answers_per_question']
            if int(question['answers_per_question']) > 0:
                questions_with_gtzero_budget += 1
            else:
                questions_with_zero_budget += 1
        self.assertEqual(questions_with_zero_budget, 1)
        self.assertEqual(questions_with_gtzero_budget, 1)
        



        

if __name__ == '__main__':
    unittest.main()