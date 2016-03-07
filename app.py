import os, sys, traceback
from flask import Flask
from flask.ext.cors import CORS
from flask.ext.mongoengine import MongoEngine
from flask.ext.restful import Api
from flask.ext.security import Security, MongoEngineUserDatastore, login_required, login_user, current_user
from flask.ext.security.registerable import register_user
from flask.ext.mail import Mail
import redis
import uuid

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

#TESTING REDIS
app.redis = redis.StrictRedis.from_url(app.config['REDIS_URL'])
db = MongoEngine(app)
api = Api(app)

app.config['CORS_HEADERS'] = 'Content-Type'
cors = CORS(app, resources={"/assign_next_question": {"origins": "*"},
                            "/answers":  {"origins": "*"}})


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

@app.before_first_request
def setup_logging():
    if not app.debug:   
        import logging
        app.logger.addHandler(logging.StreamHandler())
        app.logger.setLevel(logging.ERROR)


@app.before_first_request
def add_test_users():
    try:
        test_user = schema.requester.Requester.objects.get(
            email='dan@crowdlab.com')
    except:
        test_user = register_user(email='dan@crowdlab.com',
                                  password='chrisisawesome')

@app.route('/')
@login_required
def hello():
    # Print 
#   print "Firing the missiles..."
#   try:
#       test_user = schema.requester.Requester.objects.get(
#           email='dan@crowdlab.com')
#   except:
#       test_user = register_user(email='dan@crowdlab.com',
#                                 password='chrisisawesome')

#   return 'Hello World! Dan Weld has been added to the DB!'
    if current_user.is_authenticated():
        requester = schema.requester.Requester.objects.get_or_404(
            email=current_user.email)
        return 'Hello World! Your username is %s.<br/> Your authentication token is %s. <br/> Your requester_id is %s. <br/>' % (current_user.email,
                               current_user.get_auth_token(),
                                                                                                               requester.id)
    else:
        return "Hello World! You're not logged in, must be testing"

@app.route('/token')
@login_required
def give_me_my_token():
    """
    Requester needs to save this auth token in order to use the API.
    """
    return current_user.get_auth_token()

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
api.add_resource(QuestionApi, '/questions/<question_id>') #UNSECURED
api.add_resource(QuestionListApi, '/questions') 
api.add_resource(QuestionAnswersApi, '/questions/<question_id>/answers') #UNSECURED

# next question
from api.assignment_api import *
api.add_resource(NextQuestionApi, '/assign_next_question') #DOES NOT REQUIRE SECURITY

#TODO not implemented yet
from api.aggregation_api import *
api.add_resource(AnswerAggregationApi, '/aggregated_answer') #UNSECURED

from api.answer_api import *
api.add_resource(AnswerApi, '/answers/<answer_id>') #UNSECURED
api.add_resource(AnswerListApi, '/answers') #DOES NOT REQUIRE SECURITY

from api.task_api import *
api.add_resource(TaskApi, '/tasks/<task_id>') #UNSECURED
api.add_resource(TaskListApi, '/tasks') 
api.add_resource(TaskQuestionsApi, '/tasks/<task_id>/questions') #UNSECURED
api.add_resource(TaskSetBudget, '/tasks/set_budget')
api.add_resource(TaskDelete, '/tasks/delete')


from api.worker_api import *
api.add_resource(WorkerListApi, '/workers') #UNSECURED
api.add_resource(WorkerApi, '/workers/<worker_id>') #UNSECURED
api.add_resource(WorkerAnswersApi, '/workers/<worker_id>/answers') #UNSECURED
#TODO not implemented yet
#api.add_resource(WorkerSkillApi, '/workers/<worker_id>/skill')
#api.add_resource(WorkerPerTaskSkillApi, '/workers/<worker_id>/skill/<task_id>')

from api.requester_api import *
api.add_resource(RequesterListApi, '/requesters') #UNSECURED
api.add_resource(RequesterApi, '/requesters/<requester_id>') #UNSECURED
api.add_resource(RequesterTasksApi, '/requesters/<requester_id>/tasks') #UNSECURED
