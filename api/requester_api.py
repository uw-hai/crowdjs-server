from flask.ext.restful import Resource, reqparse
import json
from schema.requester import Requester
from schema.task import Task
from flask.ext.security.registerable import register_user

requester_parser = reqparse.RequestParser()
requester_parser.add_argument('email', type=str, required=True)
requester_parser.add_argument('password', type=str, required=True)

class RequesterListApi(Resource):
    def get(self):
        """
        Get list of all requesters.
        """
        requesters = Requester.objects
        return json.loads(requesters.to_json())
    def put(self):
        """
        Create a new requester.

        :param str email: requester email address
        :param str password: requester password

        :returns: JSON with requester_id string to use in future requests.

        **Example response:**

        .. code-block:: json

            {
                "requester_id": "12345"
            }

        """
        #TODO password security???
        args = requester_parser.parse_args()
        email = args['email']
        password = args['password']
        register_user(email=email, password=password)
        # TODO best way to return requester's ID?
        requesterDocument = Requester.objects.get_or_404(email=email)
        if requesterDocument:
            return {'requester_id' : str(requesterDocument.id)}
        else:
            return requesterDocument

class RequesterApi(Resource):
    def get(self, requester_id):
        """
        Get data of specific requester.
        """
        requester = Requester.objects.get_or_404(id=requester_id)
        return json.loads(requester.to_json())


class RequesterTasksApi(Resource):
    def get(self, requester_id):
        """
        Get all tasks by the given requester.
        """
        r = Requester.objects.get_or_404(id=requester_id)
        tasks = Task.objects(requester=r.id)
        return json.loads(tasks.to_json())
