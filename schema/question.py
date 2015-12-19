from app import db

class Question(db.Document):
    name = db.StringField(unique=True)
    description = db.StringField()
    #TODO allow storing arbitrary data (i.e. photo)
    data = db.StringField()
    task = db.ReferenceField('Task')
    valid_answers = db.ListField(db.StringField(), default=[])
    requester = db.ReferenceField('Requester')
    # strategy -> answer mapping
    inference_results = db.DictField()

    answers_per_question = db.IntField()
