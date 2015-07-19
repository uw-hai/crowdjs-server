from flask.ext.security import UserMixin
from hello import db
from role import Role

class Requester(db.Document, UserMixin):
    email = db.StringField(required=True)
    roles = db.ListField(db.ReferenceField(Role), default=[])
