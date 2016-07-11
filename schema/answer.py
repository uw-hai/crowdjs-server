from app import db

class Answer(db.DynamicDocument):
    value = db.StringField()
    question = db.ReferenceField('Question')
    task = db.ReferenceField('Task')
    worker = db.ReferenceField('Worker')
    status = db.StringField(choices=('Assigned', 'Completed'))
    assign_time = db.DateTimeField()
    complete_time = db.DateTimeField()
    requester = db.ReferenceField('Requester')

    #If this answer is alive, then it should be considered in the
    # "current" assigning "session."
    #In other words, it should be counted towards any
    #budget that is currently in place.
    is_alive = db.BooleanField()
