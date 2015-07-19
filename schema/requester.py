from hello import db

class Requester(db.Document):
    email = db.StringField(required=True)
