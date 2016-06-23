from app import db

class Task(db.Document):
    name = db.StringField(max_length=80)
    description = db.StringField(max_length=255)
    requester = db.ReferenceField('Requester')

    #This field is for the requester to store whatever they want.
    data = db.StringField()

    #How long a worker has to work on a question in this task
    #in seconds
    assignment_duration = db.IntField()
    
    total_task_budget = db.IntField()
    
