from app import db

class Worker(db.Document):
    turk_id = db.StringField()
