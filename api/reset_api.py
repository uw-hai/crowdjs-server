from flask.ext.restful import reqparse, abort, Api, Resource
from schema.answer import Answer
import json
from flask.ext.security import login_required, current_user, auth_token_required

###
# THIS WHOLE FILE IS UNTESTED
###
reset_parser = reqparser.RequestParser()
reset_parser.add_argument('task_id', type=str, required=True)
reset_parser.add_argument('requester_id', type=str, required=True)
class ResetApi(Resource):

    @auth_token_required
    def post(self):
        args = reset_parser.parse_args()
        task_id = args['task_id']
        requester_id = args['requester_id']

        if not requester_token_match(requester_id):
            return "Sorry, your api token is not correct"

        all_answers = Answer.objects(requester = requester_id,
                                     task = task_id)
        for answer in all_answers:
            answer.is_alive = False
            answer.save()

        return "Task %s reset." % task_id
