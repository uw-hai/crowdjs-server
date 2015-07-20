from app import db
from worker import Worker
from requester import Requester
from question import Question

class Answer(db.Document):
    value = db.StringField()
    question = db.ReferenceField(Question)
    worker = db.ReferenceField(Worker)
    requester = db.ReferenceField(Requester)
