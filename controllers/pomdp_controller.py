import datetime
import numpy as np
import pomdp
import pomdp_peng
import pomdp_policy
import util
import schema
import os
import shutil

from aggregation.db_inference import aggregate_task_EM
from app import app
from redis_util import *

class POMDPController():
    """
    Question assignment controller with POMDP-based assignment and label decisions

    Usage of this object:

    __init__:
        created on /assign API request w/worker=W, task=T
        runs EM on all observation in Task T
        solves/retrieves pomdp policy w EM avg gamma
    assign:
        calculates belief state and action-reward pairs for each question in T
        returns best assignment W:Question Q
        updates Redis that worker W has been assigned to Q
    getStatus:
        calculates belief state and action-reward pairs for each question in T
        returns 

    See getPolicy() for information on POMDP policy solving and caching.
    """
    def __init__(self, task_id, discount=0.9999, timeout=300, reward_incorrect=-50):
        # XXX assumes task_id has been checked already
        self.task_id = task_id
        self.task = schema.task.Task.objects.get(id=task_id)

        #1)Run EM
        EM_results = aggregate_task_EM(task_id)
        print EM_results

        #2)Get avg gamma from EM results, if none default to 1.0
        self.average_gamma = self.getAverageGamma(EM_results)
        print self.average_gamma

        #3)Create POMDP policy

        # Parameters
        self.discount = discount
        self.timeout = timeout # seconds
        self.reward_incorrect = reward_incorrect
       
        # Constants
        self.reward_correct = 0
        self.reward_create = -1
        self.num_difficulty_bins = 11  # 0.0-1.0
        self.num_answer_choices = 2  # either 0 or 1
        self.num_states = 1 + self.num_difficulty_bins * self.num_answer_choices # includes terminal state

        # XXX POMDP weird stuff
        self.policy_dir = 'policies'
        if not os.path.isdir(self.policy_dir):
            #make the directory if it doesn't exist
            os.makedirs(self.policy_dir)

        self.pomdp_var = pomdp_peng.PengPOMDP(
            self.num_difficulty_bins, self.average_gamma)

        # Initialize pomdp policy with given parameters
        self.policy = self.getPolicy()

    def getStatus(self, includeVotes=True):
        """
        Returns all observations and pomdp opinions of question status
        """
        #1) Calculate beliefs
        beliefs = self.calculateBeliefs()

        #2) Get POMDP data for each question
        out = {}
        for (q_id,belief) in beliefs.iteritems():

            #get POMDP action reward pairs
            action_rewards = {str(a):r for a,r in self.policy.get_action_rewards(belief).iteritems()}

            #which action has best expected reward
            best_action, best_expected_reward = self.policy.get_best_action(belief)

            #get best action as readable string (submit-true, etc.)
            best_action_str = self.pomdp_var.actions[best_action]

            #get all votes on this question as JSON
            answers = self.getQuestionCompletedAnswers(q_id)
            votes = []
            for answer in answers:
                q_name = answer.question.name
                w_id = str(answer.worker.id)
                w_platform_id = str(answer.worker.platform_id)
                w_skill = answer.worker.inference_results['EM']['skill']
                value = answer.value
                vote = {"worker_id": w_id, "worker_platform_id":w_platform_id, "est_skill":w_skill, "value":value}
                votes.append(vote)

            out[q_id] = dict(best_action=best_action, best_expected_reward=best_expected_reward, action_rewards=action_rewards, best_action_str=best_action_str, votes=votes)
            if not includeVotes:
                out[q_id].pop('votes')

        print out
        return out

    def assign(self, available_workers):
        """
        Provide assignments to a list of available workers - 
        note that this strategy only supports assigning one worker at a time.

        Assumes a worker cannot answer the same question more than once
        and that there are no per-question budgets
        """
        
        status = self.getStatus()

        assert len(available_workers) == 1
        worker = available_workers[0]
        assignment = {}

        w_id = str(worker.id)
        task_id = self.task_id

        #tracks 
        worker_assignments_var = redis_get_worker_assignments_var(task_id, w_id)

        print "WORKER ID:", w_id
        print "STATUS:", status
        print "ASSIGNMENTS FOR WORKER SO FAR:", app.redis.smembers(worker_assignments_var)


        # sort questions by pomdp expected reward...
        # XXX this isn't quite what we want...
        # want to sort by value of getting another label
        # so we don't have all workers getting assigned to the same question
        unfinished_unsorted_qs = [(q,v) for (q,v) in status.iteritems() if v['best_action_str'] == 'create-another-job']
        # NOTE REVERSE ORDER
        sorted_qs = sorted(unfinished_unsorted_qs, key=lambda x:x[1]['best_expected_reward'], reverse=True)
        print "sorted_qs", sorted_qs
        print "worker %s has done the following questions" % w_id
        for (q_id,er) in sorted_qs:
            if app.redis.sismember(worker_assignments_var, q_id):
                print "+", q_id
            else:
                print "-", q_id

        for idx in range(len(sorted_qs)):
            q_id,expected_reward = sorted_qs[idx]

            if not app.redis.sismember(worker_assignments_var, q_id):
                assignment[w_id] = q_id
                print "assignment=", assignment
                app.redis.sadd(worker_assignments_var, q_id)
                return assignment

        #if here no assignment was made to our worker!
        assert len(assignment) == 0
        print "no assignment made yet"

        #NOTE POMDP doesn't think there are any questions available to the worker 
        #that need another label, but let's give them an assignment anyway
        #Pick question where submitting would have worst expected reward 
        # (implying it may benefit from another label)
        finished_qs = [(q,v) for (q,v) in status.iteritems() if v['best_action_str'] != 'create-another-job'] #TODO
        sorted_finished_qs = sorted(finished_qs, key=lambda x:x[1]['best_expected_reward']) # no reverse
        for idx in range(len(sorted_finished_qs)):
            q_id,expected_reward = sorted_finished_qs[idx]

            if not app.redis.sismember(worker_assignments_var, q_id):
                assignment[w_id] = q_id
                print "gave worker a finished q assignment=", assignment
                app.redis.sadd(worker_assignments_var, q_id)
                return assignment

        return assignment

    # Helper methods (ideally not exposed)

    def calculateBeliefs(self):
        """Calculate belief states for each question in the task.
        Uses latest estimate of worker skills from DB
        """

        belief = {}

        for question in self.getQuestions():
            q = str(question.id)
            belief[q] = self.HELPER_init_belief()

            print belief[q]
            for answer in self.getQuestionCompletedAnswers(question):
                print q
                print str(answer.question.id)
                assert str(answer.question.id) == q
                w_skill = answer.worker.inference_results['EM']['skill']
                # answer.value must be "0" or "1"
                assert answer.value == "0" or answer.value == "1"
                print answer.value, w_skill
                belief[q] = self.HELPER_update_belief(belief[q], answer.value, w_skill)
                print belief[q]

        print "Question beliefs:", belief
        print "##################"
        return belief


    def getAverageGamma(self, EM_results):
        """
        Helper
        """
        if len(EM_results['workers']) == 0:
            avg_gamma = 1.0
        else:
            avg_gamma = np.mean(EM_results['workers'].values())
        print "New average gamma:", avg_gamma
        return avg_gamma

    def getCompletedAnswers(self):
        return schema.answer.Answer.objects(task=self.task, status='Completed')

    def getQuestionCompletedAnswers(self, question):
        return schema.answer.Answer.objects(task=self.task, status='Completed', question=question)

    def getQuestions(self):
        return schema.question.Question.objects(task=self.task)

    def getPolicy(self):
        """
        Solve POMDP policy based on current parameters
        """
        # NOTE Naming scheme of POMDP policy files:
        # dai_<worker skill rounded to 0.1>_<reward for incorrect answer>.policy
        # i.e. 'dai_1.0_-100' is the policy for the Dai-AIJ13 pomdp with
        # average worker skill = 1.0 and reward for incorrect answer of -100
        filename = 'dai_%.1f_%s.policy' % (self.average_gamma, self.reward_incorrect)
        if os.path.isdir(self.policy_dir) and os.path.isfile(self.policy_dir + '/' + filename):
            #previously solved
            policy = pomdp_policy.POMDPPolicy(self.policy_dir + '/' + filename, file_format='zmdp', n_states= self.num_states)
        else:
            #have to solve it
            zpomdp = pomdp.ZPOMDP()
            policy = zpomdp.solve(self.pomdp_var.states, self.pomdp_var.actions, self.pomdp_var.observations,
                                  self.pomdp_var.CLOSURE_f_start(self.num_states),
                                  self.pomdp_var.f_transition,
                                  self.pomdp_var.CLOSURE_f_observation(self.average_gamma),
                                  self.pomdp_var.CLOSURE_f_reward(self.reward_create, self.reward_correct, self.reward_incorrect),
                                  discount=self.discount, timeout=self.timeout, directory=self.policy_dir)

            #save our new policy where we can find it again
            #rename p.policy to filename w/params
            shutil.move(self.policy_dir + '/p.policy', self.policy_dir + '/' + filename)
        return policy

    def HELPER_update_belief(self, old_belief, observation, gamma):
        """
        Update belief for question q_id based on observation by worker with skill=gamma
        Will convert observation to integer 1 or 0 if it is a string
        """
        observation = int(observation)
        print "old_belief:", old_belief, type(old_belief)
        print "observation:", observation, type(observation)
        print "gamma:", gamma, type(gamma)

        diffs = [0.1*i for i in range(self.num_difficulty_bins)]
        new_belief = util.updateBelief(old_belief, None, observation, diffs, gamma)
        print "new_belief", new_belief, type(new_belief)
        return new_belief

    def HELPER_init_belief(self):
        """
        Uniform over non-terminal states, append terminal state w/p=0
        """
        return util.initBelief(self.num_answer_choices, self.num_difficulty_bins)
