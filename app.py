import os
from flask import Flask
from flask.ext.mongoengine import MongoEngine

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

db = MongoEngine(app)

from schema.requester import Requester

@app.route('/')
def hello():
    test_requester = Requester(email='dan@weld.com')
    test_requester.save()
    return 'Hello World! Dan Weld has been added to the DB!'


