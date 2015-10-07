import os, sys, traceback
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.restful import Api
from flask.ext.security import Security, MongoEngineUserDatastore, login_required, login_user
from flask.ext.security.registerable import register_user
from flask.ext.mail import Mail
import uuid

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

db = MongoEngine(app)
api = Api(app)

import schema.requester
import schema.question
import schema.task
import schema.role

print "Loading mail extension"
sys.stdout.flush()
mail = Mail(app)

print "Loading security datastore"
sys.stdout.flush()
user_datastore = MongoEngineUserDatastore(db, schema.requester.Requester, 
                                          schema.role.Role)
security = Security(app, user_datastore)
print "Done loading security datastore. Ready to serve pages."
sys.stdout.flush()

@app.route('/')
def hello():
    print "Firing the missiles..."
    try:
        test_user = schema.requester.Requester.objects.get(
            email='dan@crowdlab.com')
    except:
        test_user = register_user(email='dan@crowdlab.com',
                                  password='chrisisawesome')

    return 'Hello World! Dan Weld has been added to the DB!'

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return "You have been logged out."

@app.route('/add_test_questions_and_task')
@login_required
def add_test_questions_and_task():
    test_requester = schema.requester.Requester.objects.get_or_404(
        email='dan@weld.com')
    test_question1_name = uuid.uuid1().hex
    test_question1 = schema.question.Question(name=test_question1_name,
                                             description='test question 1',
                                             requester = test_requester)
    test_question1.save()

    test_question2_name = uuid.uuid1().hex
    test_question2 = schema.question.Question(name=test_question2_name,
                                             description='test question 2',
                                             requester = test_requester)

    test_question2.save()

    test_task_name = uuid.uuid1().hex
    test_task = schema.task.Task(name = test_task_name,
                                 description = 'test task with 2 questions',
                                 requester = test_requester,
                                 questions = [test_question1, test_question2])
    test_task.save()
                                
    return 'Test questions and task added to DB'

                                 
    
# API routes go here.

from api.question_api import *
api.add_resource(QuestionApi, '/questions/<question_id>')
api.add_resource(QuestionListApi, '/questions')
api.add_resource(QuestionAnswersApi, '/questions/<question_id>/answers')
#TODO not implemented yet
#api.add_resource(QuestionAggregatedAnswerApi, '/questions/<question_id>/aggregated_answer')

from api.answer_api import *
api.add_resource(AnswerApi, '/answers/<answer_id>')
api.add_resource(AnswerListApi, '/answers')

from api.task_api import *
api.add_resource(TaskApi, '/tasks/<task_id>')
api.add_resource(TaskListApi, '/tasks')
api.add_resource(TaskQuestionsApi, '/tasks/<task_id>/questions')

from api.worker_api import *
api.add_resource(WorkerListApi, '/workers')
api.add_resource(WorkerApi, '/workers/<worker_id>')
api.add_resource(WorkerAnswersApi, '/workers/<worker_id>/answers')
#TODO not implemented yet
#api.add_resource(WorkerSkillApi, '/workers/<worker_id>/skill')
#api.add_resource(WorkerPerTaskSkillApi, '/workers/<worker_id>/skill/<task_id>')

from api.requester_api import *
api.add_resource(RequesterListApi, '/requesters')
api.add_resource(RequesterApi, '/requesters/<requester_id>')
api.add_resource(RequesterTasksApi, '/requesters/<requester_id>/tasks')
