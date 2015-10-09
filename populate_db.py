# Usage: > python populate_db.py server_address:port
import requests, json, sys

#XXX Testing (true black box wouldn't be able to clear DB like this)
from app import schema
def clear_db():
    schema.answer.Answer.objects().delete()
    schema.question.Question.objects().delete()
    schema.requester.Requester.objects().delete()
    schema.role.Role.objects().delete()
    schema.task.Task.objects().delete()
    schema.worker.Worker.objects().delete()

print("Clearing DB (cheating)")
# CLEAR THE DATABASE
clear_db()
print("DB cleared.")
#/XXX

print("Populating DB...")

URL_ROOT = sys.argv[1]
JSON_HEADERS = {'Content-type' : 'application/json'}

requester_id = 'requester_id'
answer_id = 'answer_id'
worker_id = 'worker_id'
task_id = 'task_id'
question_id = 'question_id'

requester_url = '/requesters'
answer_url = '/answers'
worker_url = '/workers'
task_url = '/tasks'
question_url = '/questions'


def put(url, data):
    """
    Sends a PUT request to given URL with the given data as JSON.
    Returns the response.
    """
    resp = requests.put(URL_ROOT + url, json=data)
    return resp

def put_id(url, data, id_key='id'):
    """
    Sends PUT request to given URL with given data as JSON.
    Looks in JSON response for key id_key, returns the associated value.
    """
    print("sending PUT data=%s" % data)
    resp = put(url, data)
    print("received PUT response=%s" % resp)
    ret_json = resp.json()
    print("received PUT json=%s" % ret_json)
    ID = ret_json[id_key]
    return ID

def load_requester(data):
    ID = put_id(requester_url, data, requester_id)
    return ID

def load_question(data):
    ID = put_id(question_url, data, question_id)
    return ID

def load_task(data):
    ID = put_id(task_url, data, task_id)
    return ID

def load_worker(data):
    ID = put_id(worker_url, data, worker_id)
    return ID

def load_answer(data):
    ID = put_id(answer_url, data, answer_id)
    return ID


#XXX systematic way to save IDs: return from each load_X() function
requester1 = load_requester(dict(email = "sethv1+1@cs.uw.edu", password="badpassword"))
requester2 = load_requester(dict(email = "sethv1+2@cs.uw.edu", password="sethsbadpassword"))

# questions without task + requester (MUST BE ADDED AS PART OF A TASK)
question1 = dict(question_name = "q1 name", question_description = "q1 desc", question_data = "data11111",
                valid_answers = ["cat", "dog"])
question2 = dict(question_name = "q2 name", question_description = "q2 desc", question_data = "data22222")

#Add tasks
task1 = load_task(dict(task_name = "test task w/preloaded Qs", task_description = "description here",
                requester_id = requester1, questions = [question1, question2]))

#XXX set question1, question2 to be their respective question IDs. How?
# Need their IDs to be able to answer them.

task2 = load_task(dict(task_name = "test task where questions loaded later", task_description = "t2 desc",
                requester_id = requester2))

# add questions 3-5 to task2
question3 = load_question(dict(question_name = "q3 name", question_description = "q3 desc", question_data = "data3333333333",
                        task_id = task2, requester_id = requester2))
question4 = load_question(dict(question_name = "q4 name", question_description = "q4 desc", question_data = "data4444444444444",
                        task_id = task2, requester_id = requester2))
question5 = load_question(dict(question_name = "q5 name", question_description = "q5 desc", question_data = "data55555",
                        task_id = task2, requester_id = requester2, valid_answers = ["animal", "vegetable", "mineral"]))

# Add workers and answers

worker1 = load_worker(dict(turk_id = "turk1"))
worker2 = load_worker(dict(turk_id = "turk2"))
worker3 = load_worker(dict(turk_id = "turk3"))

#answer1 = load_answer(dict(value = "dog", question_id = question1, worker_id = worker1))
#answer2 = load_answer(dict(value = "dog", question_id = question2, worker_id = worker1))

#answer3 = load_answer(dict(value = "cat", question_id = question1, worker_id = worker2))
answer4 = load_answer(dict(value = "husky", question_id = question5, worker_id = worker2))

#answer5 = load_answer(dict(value = "blue cat", question_id = question1, worker_id = worker3))
answer6 = load_answer(dict(value = "apple", question_id = question3, worker_id = worker3))
answer7 = load_answer(dict(value = "biscuit", question_id = question4, worker_id = worker3))
answer8 = load_answer(dict(value = "husky dog", question_id = question5, worker_id = worker3))

print("Done populating DB.")
