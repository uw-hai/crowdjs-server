from flask.ext.security import UserMixin
from app import db

class Requester(db.Document, UserMixin):
    email = db.StringField(required=True)
    roles = db.ListField(db.ReferenceField('Role'), default=[])
