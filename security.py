from flask import current_app
from flask.ext.security import Security, MongoEngineUserDatastore

from app import db
from schema.requester import Requester
from schema.role import Role

user_datastore = MongoEngineUserDatastore(db, Requester, Role)
security = Security(current_app, user_datastore)
