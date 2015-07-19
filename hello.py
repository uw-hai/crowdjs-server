import os
from flask import Flask
from flask.ext.mongoengine import MongoEngine

app = Flask(__name__)

app.config.from_object(os.environ['APP_SETTINGS'])

db = MongoEngine(app)

class Requester(db.Document):
    email = db.StringField(required=True)
    
test_requester = Requester(email='dan@weld.com')
test_requester.save()


@app.route('/')
def hello():
    return 'Hello World!'


