from app import db

class Worker(db.DynamicDocument):
    platform_id = db.StringField()
    platform_name = db.StringField()

    # Mapping inference strategy -> result
    # Example format:
    # strategy : {'timestamp' : timestamp, 'skill' : skill_estimate}
    inference_results = db.DictField()
