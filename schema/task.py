from app import db

class Task(db.Document):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
    requester = db.ReferenceField('Requester')
