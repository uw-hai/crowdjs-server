from flask.ext.restful import reqparse, abort, Api, Resource
from flask.ext.security import auth_token_required
from flask import url_for
from schema.answer import Answer
from schema.question import Question
from schema.worker import Worker
import json
from collections import Counter
from schema.inferenceJob import InferenceJob
from util import get_requester_document, get_task_document, requester_token_match, requester_task_match, start_inference_job

answer_agg_parser = reqparse.RequestParser()
answer_agg_parser.add_argument('question_name', type=str, required=True)
answer_agg_parser.add_argument('strategy', type=str, required=True)

class AnswerAggregationApi(Resource):
    def get(self):
        """
        Get list of all answers.
        """
        args = answer_agg_parser.parse_args()
        question_name = args['question_name']
        strategy = args['strategy']
        
        question = Question.objects.get_or_404(name=question_name)

        # call
        aggregated_answer = self.aggregated_answer(question, strategy)

        # save aggregation result (strategy, answer) in DB
        # TODO decide when to update inference results for each strategy,
        # currently doing it lazily.
        question.inference_results[strategy] = aggregated_answer
        question.save()

        return {'question_id': str(question.id),
                'aggregated_answer': str(aggregated_answer)}

    def aggregated_answer(self, question, strategy):
        if strategy == 'majority_vote':
            return self.majority_vote(question)
        else:
            return None

    def majority_vote(self, question):
        """
        Returns the most common answer to the given question.
        """
        answers = Answer.objects(question=question)
        values = []
        for answer in answers:
            values.append(answer.value)

        counts = Counter(values)
        return counts.most_common(1)[0][0]

# parser for starting aggregation jobs
task_agg_start_parser = reqparse.RequestParser()
task_agg_start_parser.add_argument('strategy', type=str, default='majority_vote')
task_agg_start_parser.add_argument('requester_id', type=str, required=True) # TODO eliminate

# parser for getting status of aggregation jobs
task_agg_get_parser = reqparse.RequestParser()
task_agg_get_parser.add_argument('requester_id', type=str, required=True) # TODO eliminate

class TaskAggregationApi(Resource):
    """
    Task-level label aggregation/inference
    """
    
    @auth_token_required
    def put(self, task_id):
        """
        Start an aggregation/inference job on this task
        args: strategy
        Returns: JSON representation of this job as created
        """
        # TODO make this POST because it creates a resource
        # TODO would also be nice to return URL location for job

        args = task_agg_start_parser.parse_args()
        print args
        strategy = args['strategy']
        requester_id = args['requester_id']

        # check that requester and task info is valid
        if not requester_token_match(requester_id):
            return {'error': 'token does not match requester id'}

        requester = get_requester_document(requester_id)

        if not requester:
            return {'error': 'you are not a requester'}

        if not requester_task_match(requester_id, task_id):
            return {'error': 'you do not own this task'}

        task = get_task_document(task_id)

        # create job in DB
        job_doc = InferenceJob(requester = requester, task = task, strategy = strategy)
        job_doc.save()

        job_id = str(job_doc.id)

        ret_val = json.loads(job_doc.to_json())

        # TODO start job in background
        start_inference_job(job_id)

        return ret_val

    @auth_token_required
    def get(self, task_id, job_id):
        """
        Get info of a given aggregation/inference job that is running/ran on the specified task

        Returns: json representation of job, possibly with inference results or an unfinished status
        """

        args = task_agg_get_parser.parse_args()
        requester_id = args['requester_id']

        #TODO copied from above, refactor into utility fn
        # check that requester and task info is valid
        if not requester_token_match(requester_id):
            return {'error': 'token does not match requester id'}

        requester = get_requester_document(requester_id)

        if not requester:
            return {'error': 'you are not a requester'}

        if not requester_task_match(requester_id, task_id):
            return {'error': 'you do not own this task'}

        # get job from DB
        job_doc = InferenceJob.objects.get_or_404(id = job_id)

        return json.loads(job_doc.to_json())
