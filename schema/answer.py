from app import db

class Answer(db.Document):
    value = db.StringField()
    question = db.ReferenceField('Question')
    worker = db.ReferenceField('Worker')
    status = db.StringField(choices=('Assigned', 'Completed'))
    assign_time = db.DateTimeField()
    complete_time = db.DateTimeField()
