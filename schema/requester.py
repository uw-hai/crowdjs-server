from flask.ext.security import UserMixin
from app import db

class Requester(db.Document, UserMixin):
    email = db.StringField(required=True)
    password = db.StringField(required=True)
    active = db.BooleanField(default=True)
    confirmed_at = db.DateTimeField()
    roles = db.ListField(db.ReferenceField('Role'), default=[])
