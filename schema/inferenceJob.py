from app import db

class InferenceJob(db.DynamicDocument):
    """
    Stores results of some inference/aggregation algorithm run on a task
    """

    #main fields
    requester = db.ReferenceField('Requester')
    task = db.ReferenceField('Task')
    strategy = db.StringField(max_length=80) # algorithm to run
    results = db.DynamicField() # NOTE results can be written in any format for now
    status = db.StringField(choices=('Created','Running','Completed','Killed'), default='Created')

    #optional
    additional_params = db.StringField(max_length=80, default="") # additional arguments for algorithm

    #TODO other possible fields: timeout, created_time, completed_time, run_time, ...
