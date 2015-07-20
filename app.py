import os
from flask import Flask
from flask.ext.mongoengine import MongoEngine
from flask.ext.restful import Api

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

db = MongoEngine(app)
api = Api(app)

import schema.requester
import schema.question

@app.route('/')
def hello():
    test_requester = schema.requester.Requester(email='dan@weld.com')
    test_requester.save()
    return 'Hello World! Dan Weld has been added to the DB!'

@app.route('/add_test_question')
def add_test_question():
    test_requester = schema.requester.Requester.objects.get_or_404(
        email='dan@weld.com')
    test_question = schema.question.Question(name='testing',
                                             requester = test_requester)
    test_question.save()
    return 'Test question added to DB'

@app.route('/add_test_worker')
def add_test_worker():
    test_worker = schema.worker.Worker(turk_id='dan_weld_the_worker')
    test_worker.save()
    return 'Test worker added to DB'
    

from api.question import QuestionApi
api.add_resource(QuestionApi, '/questions/<question_id>')

from api.answer_api import AnswerApi
api.add_resource(AnswerApi, '/api/add_answer')
