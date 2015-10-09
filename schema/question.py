from app import db

class Question(db.Document):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
    #TODO allow storing arbitrary data (i.e. photo)
    data = db.StringField(max_length=255)
    task = db.ReferenceField('Task')
    valid_answers = db.ListField(db.StringField, default=[])
    requester = db.ReferenceField('Requester')
