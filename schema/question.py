from flask.ext.security import RoleMixin
from hello import db
from answer import Answer

class Question(db.Document):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
    worker_answers = db.ListField(db.ReferenceField(Answer), default=[])
    valid_answers = db.ListField(db.StringField, default=[])

