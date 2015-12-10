from app import db

class Worker(db.Document):
    platform_id = db.StringField()
    platform_name = db.StringField()
