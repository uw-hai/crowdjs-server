import datetime
import numpy as np
import pomdp
import pomdp_peng
import pomdp_policy
import util
import os
import shutil
import importlib
inf_mod = importlib.import_module("crowd-estimate.em")


class expPOMDPController():
    """
    Question assignment controller with POMDP-based assignment and label decisions
    Replicates server controller without DB

    Args:
        settings: dict with keys i.e. 'discount':0.99, 'reward_incorrect':-100

    Usage of this object:

    __init__:
        created on /assign API request w/worker=W, task=T
        runs EM on all observation in Task T
        solves/retrieves pomdp policy w EM avg gamma
    assign:
        calculates belief state and action-reward pairs for each question in T
        returns best assignment W:Question Q
        updates that worker W has been assigned to Q
    addObservation:
        add an observation in JSON format
    getStatus:
        calculates belief state and action-reward pairs for each question in T
        returns 

    See getPolicy() for information on POMDP policy solving and caching.
    """
    def __init__(self, settings={}):



        #3)Create POMDP policy

        # Parameters
        self.discount = settings.get('discount', 0.9999)
        self.timeout = settings.get('timeout', 300) # seconds
        self.reward_incorrect = settings.get('reward_incorrect', -50)
       
        # Constants
        self.reward_correct = 0
        self.reward_create = -1
        self.num_difficulty_bins = 11  # 0.0-1.0
        self.num_answer_choices = 2  # either 0 or 1
        self.num_states = 1 + self.num_difficulty_bins * self.num_answer_choices # includes terminal state

        #Init skill/diff estimates
        #Init belief/worker assignments/labels

        self.workers = settings.get('worker_ids', [])
        self.questions = settings.get('question_names', [])
        self.em_workers = {}
        self.em_questions = {}
        for w_id in self.workers:
            self.em_workers[w_id] = {'skill': None}
        for q_id in self.questions:
            self.em_questions[q_id] = {'difficulty': None}

        print "workers:", self.workers
        print "questions:", self.questions

        self.worker_assignments_var = {w_id:set() for w_id in self.workers} #map w_id:set of questions w_id has been assigned to
        self.votes = {q_id:[] for q_id in self.questions} #map q_id:observations for q
        self.em_votes = {}
        self.belief = {q_id:self.calculateQuestionBelief(q_id) for q_id in self.questions}
        self.run_em()

        # XXX POMDP weird stuff
        self.policy_dir = 'policies'
        if not os.path.isdir(self.policy_dir):
            #make the directory if it doesn't exist
            os.makedirs(self.policy_dir)

        self.pomdp_var = pomdp_peng.PengPOMDP(
            self.num_difficulty_bins, self.average_gamma)

        # Initialize pomdp policy with given parameters
        self.policy = self.getPolicy()

    def run_em(self):
        #XXX Updates self.em_estimates
        res = inf_mod.estimate(self.em_votes, self.em_workers, self.em_questions)
        print "EM Result:"
        print res
        self.em_estimates = res
        self.average_gamma = self.getAverageGamma(res)

    def addObservation(self, data):
        """Add json observation"""
        w = data["worker_id"]
        q = data["question_name"]
        label = data["value"]

        self.votes[q].append(data)

        self.em_votes[(w,q)] = {'vote':label}

        #update question belief
        self.belief[q] = self.calculateQuestionBelief(q)
        #update EM
        # XXX TODO note should probably not run on every new observation
        # unless we have incremental EM
        self.run_em()

        #update policy
        self.getPolicy()

    def getStatus(self, includeVotes=False):
        """
        Returns all observations and pomdp opinions of question status
        """
        #1) Calculate beliefs
        #TODO want to cache beliefs and make incremental updates
        print "Calculating beliefs"
        beliefs = self.belief

        #2) Get POMDP data for each question
        print "Getting POMDP decision for each question"
        out = {}
        for (q_id,belief) in beliefs.iteritems():
            print "q_id", q_id

            #get POMDP action reward pairs
            action_rewards = {str(a):r for a,r in self.policy.get_action_rewards(belief).iteritems()}

            #which action has best expected reward
            best_action, best_expected_reward = self.policy.get_best_action(belief)

            #get best action as readable string (submit-true, etc.)
            best_action_str = self.pomdp_var.actions[best_action]

            out[q_id] = dict(best_action=best_action,
                            best_expected_reward=best_expected_reward,
                            best_action_str=best_action_str,
                            action_rewards=action_rewards)

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

        w_id = worker

        print "WORKER ID:", w_id
        print "STATUS:", status
        print "ASSIGNMENTS FOR WORKER SO FAR:", self.worker_assignments_var[w_id]

        # sort questions by pomdp expected reward...
        # XXX this isn't quite what we want...
        # want to sort by value of getting another label
        # so we don't have all workers getting assigned to the same question
        unfinished_unsorted_qs = [(q,v) for (q,v) in status.iteritems() if v['best_action_str'] == 'create-another-job']
        # NOTE REVERSE ORDER
        sorted_qs = sorted(unfinished_unsorted_qs, key=lambda x:x[1]['best_expected_reward'], reverse=True)
        print "sorted_qs", sorted_qs

        for idx in range(len(sorted_qs)):
            q_id,expected_reward = sorted_qs[idx]

            if q_id not in self.worker_assignments_var[w_id]:
                assignment[w_id] = q_id
                print "assignment=", assignment
                self.worker_assignments_var[w_id].add(q_id)
                return assignment

        #if here no assignment was made to our worker!
        assert len(assignment) == 0
        print "no assignment made yet"

        #NOTE POMDP doesn't think there are any questions available to the worker 
        #that need another label, but let's give them an assignment anyway
        #Pick question where submitting would have worst expected reward 
        # (implying it may benefit from another label)
        finished_qs = [(q,v) for (q,v) in status.iteritems() if v['best_action_str'] != 'create-another-job']
        sorted_finished_qs = sorted(finished_qs, key=lambda x:x[1]['best_expected_reward']) # no reverse
        for idx in range(len(sorted_finished_qs)):
            q_id,expected_reward = sorted_finished_qs[idx]

            if q_id not in self.worker_assignments_var[w_id]:
                assignment[w_id] = q_id
                print "gave worker a finished q assignment=", assignment
                self.worker_assignments_var[w_id].add(q_id)
                return assignment

        return assignment

    # Helper methods (ideally not exposed)

    def getSkillEstimate(self, w_id):
        return self.em_estimates['workers'].get(w_id, 1.0)

    def calculateQuestionBelief(self, q):
        bq = self.HELPER_init_belief()

        for answer in self.getQuestionCompletedAnswers(q):
            w_id = answer["worker_id"]
            w_skill = self.getSkillEstimate(w_id)
            value = answer["value"]
            # answer.value must be "0" or "1"
            assert value == "0" or value == "1"
            bq = self.HELPER_update_belief(bq, value, w_skill)

        return bq

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

    def getQuestionCompletedAnswers(self, question):
        return self.votes[question]

    def getPolicy(self):
        """
        Solve POMDP policy based on current parameters
        """
        # NOTE Naming scheme of POMDP policy files:
        # dai_<worker skill rounded to 0.1>_<reward for incorrect answer>.policy
        # i.e. 'dai_1.0_-100' is the policy for the Dai-AIJ13 pomdp with
        # average worker skill = 1.0 and reward for incorrect answer of -100
        filename = 'dai_%.1f_%s.policy' % (self.average_gamma, self.reward_incorrect)
        print "Updating policy to %s..." % filename
        if os.path.isdir(self.policy_dir) and os.path.isfile(self.policy_dir + '/' + filename):
            #previously solved
            print "Policy already solved"
            policy = pomdp_policy.POMDPPolicy(self.policy_dir + '/' + filename, file_format='zmdp', n_states= self.num_states)
        else:
            #have to solve it
            print "Policy needs to be solved"
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
        #print "old_belief:", old_belief, type(old_belief)
        #print "observation:", observation, type(observation)
        #print "gamma:", gamma, type(gamma)

        diffs = [0.1*i for i in range(self.num_difficulty_bins)]
        new_belief = util.updateBelief(old_belief, None, observation, diffs, gamma)
        #print "new_belief", new_belief, type(new_belief)
        return new_belief

    def HELPER_init_belief(self):
        """
        Uniform over non-terminal states, append terminal state w/p=0
        """
        return util.initBelief(self.num_answer_choices, self.num_difficulty_bins)
