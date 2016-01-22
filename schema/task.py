from app import db

class Task(db.Document):
    name = db.StringField(max_length=80, unique=True)
    description = db.StringField(max_length=255)
    requester = db.ReferenceField('Requester')

    #This field is for the requester to store whatever they want.
    data = db.StringField()

    #These will get called everytime an answer to this task is submitted.
    global_answer_callback = db.StringField()
    global_answer_callback_url = db.StringField()
    
    total_task_budget = db.IntField()
    
