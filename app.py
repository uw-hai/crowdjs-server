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

@app.route('/add_question')
def add_question():
    test_question = schema.question.Question(name='testing')
    test_question.save()
    return 'Test question added to DB'


from api.question import QuestionApi
api.add_resource(QuestionApi, '/questions/<question_id>')
