from app import db

class Answer(db.Document):
    value = db.StringField()
    question = db.ReferenceField('Question')
    worker = db.ReferenceField('Worker')
    requester = db.ReferenceField('Requester')
