from flask.ext.security import RoleMixin
from app import db

class Role(db.DynamicDocument, RoleMixin):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
