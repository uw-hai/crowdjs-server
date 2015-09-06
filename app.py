import os, sys
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.restful import Api
from flask.ext.security import Security, MongoEngineUserDatastore, login_required, login_user
import uuid

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

db = MongoEngine(app)
api = Api(app)

import schema.requester
import schema.question
import schema.task
import schema.role

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
    sys.stdout.flush()

    try:
        test_user = schema.requester.Requester.objects.get(email='dan@weld.com')
    except:
        test_user = user_datastore.create_user(email='dan@weld.com', 
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

                                 
    

from api.question_api import QuestionApi
api.add_resource(QuestionApi, '/questions/<question_id>')

from api.answer_api import AnswerApi
api.add_resource(AnswerApi, '/api/add_answer')

from api.task_api import TaskApi
api.add_resource(TaskApi, '/api/task')
