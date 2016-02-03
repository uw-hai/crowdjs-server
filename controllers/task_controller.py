#TODO connect to DB; controller should be stateless
#this entails reading/writing all history + belief updates from/to DB
import numpy as np
import pomdp
import pomdp_peng
import util

class TaskController():
    """
    Uses POMDPs to decide when questions are solved, min answers strategy (~round robin) for question assignment
    """

    def __init__(self, question_ids, reward_incorrect, average_gamma, do_gamma_updates=True):
        # Parameters
        self.reward_incorrect = reward_incorrect
        self.average_gamma = average_gamma
        self.do_gamma_updates = do_gamma_updates

        # Constants
        self.reward_correct = 0
        self.reward_create = -1
        self.discount = 0.99
        self.timeout = 10 # seconds
        self.num_difficulty_bins = 11  # 0.0-1.0
        self.num_answer_choices = 2  # either 0 or 1
        self.num_states = 1 + self.num_difficulty_bins * self.num_answer_choices # includes terminal state

        # XXX POMDP weird stuff
        self.policy_dir = None
        self.pomdp_var = pomdp_peng.PengPOMDP(
            self.num_difficulty_bins, self.average_gamma)

        # Initialize pomdp policy with given parameters
        self.HELPER_update_policy()

        # Initialize bookkeeping for question beliefs, history
        self.belief = dict()
        self.observations = dict()
        for q_id in question_ids:
            self.belief[q_id] = self.HELPER_init_belief()
            self.observations[q_id] = dict()

    def updateEstimates(self, em_res):
        """
        Update policy based on EM results. Note: we only use average worker gamma for the POMDP
        """
        print em_res
        average_gamma = np.mean(em_res['workers'].values())

        #update POMDP policies based on new EM values
        if self.do_gamma_updates:
            print "updating average gamma to", average_gamma
            self.average_gamma = average_gamma
            self.HELPER_update_policy()

    def assign(self, available_workers):
        """
        Provide assignments to a set of available workers
        Worker is assigned a question with the least # of answers that he/she has not answered yet
        If worker has already answered all questions it will not receive an assignment
        Note that this will not allow a question q to be assigned to worker w more than once - ever
        """
        print "ASSIGN available workers =", available_workers
        assignment = {}
        q_stats = self.getStatus()
        unfinished_questions = [q[0] for q in q_stats.iteritems() if q[1]['status'] == -1]
        print "UNFINISHED QUESTIONS %d: %s" % (len(unfinished_questions), unfinished_questions)
        #Get # of answers
        counts = {}

        for q_id in unfinished_questions:
            counts[q_id] = len(self.observations[q_id])
        print "answer counts per question:", counts
        L = sorted(counts,key=counts.get)
        for w_id in available_workers:
            for i in range(len(L)):
                q_id = L[i]
                if not self.observations[q_id].has_key(w_id): #worker has not answered this question
                    assignment[w_id] = q_id
                    counts[q_id] += 1
                    L = sorted(counts, key=counts.get) #re-sort
                    break # assignment made, get out of L/questions loop
            if not assignment.has_key(w_id): #assignment not made
                print "note  Worker %d was not assigned to any question" % w_id
        print "assignment:", assignment
        return assignment

    def addObservations(self, new_observations):
        """
        Update history and beliefs with new observations
        """
        for o in new_observations:
            q_id, w_id, gamma_est, value = o
            assert not self.observations[q_id].has_key(w_id)
            self.observations[q_id][w_id] = o
            self.HELPER_update_belief(q_id, o, gamma_est)

    def get_action(self, q_id):
        """
        Return the best action and expected reward for question q_id
        """
        belief = self.belief[q_id]
        action, expected_reward = self.policy.get_best_action(belief)
        action_str = self.pomdp_var.actions[action]
        return action_str, expected_reward

    def getStatus(self):
        """
        Returns all observations and pomdp opinion's of question status
        """
        out = {}
        for q_id in self.belief:
            action_str, expected_reward = self.get_action(q_id)
            if action_str == 'create-another-job':
                status = -1
            elif action_str == 'submit-false':
                status = 0
            else:
                assert action_str == 'submit-true'
                status = 1
            votes = self.observations[q_id]
            out[q_id] = dict(status=status, votes=votes)
        return out

    # Helper methods (ideally not exposed)

    def HELPER_update_policy(self):
        """
        Update + replace self.policy - i.e. after modifying one of the POMDP parameters
        """
        zpomdp = pomdp.ZPOMDP()
        policy = zpomdp.solve(self.pomdp_var.states, self.pomdp_var.actions, self.pomdp_var.observations,
                              self.pomdp_var.CLOSURE_f_start(self.num_states),
                              self.pomdp_var.f_transition,
                              self.pomdp_var.CLOSURE_f_observation(self.average_gamma),
                              self.pomdp_var.CLOSURE_f_reward(self.reward_create, self.reward_correct, self.reward_incorrect),
                              discount=self.discount, timeout=self.timeout, directory=self.policy_dir)
        self.policy = policy

    def HELPER_update_belief(self, q_id, observation, gamma):
        """
        Update belief for question q_id based on observation by worker with skill=gamma
        """
        old_belief = self.belief[q_id]
        diffs = [0.1*i for i in range(self.num_difficulty_bins)]
        new_belief = util.updateBelief(old_belief, None, observation, diffs, gamma)
        self.belief[q_id] = new_belief

    def HELPER_init_belief(self):
        """
        Uniform over non-terminal states, append terminal state w/p=0
        """
        num_states = self.num_difficulty_bins * self.num_answer_choices
        return [1.0/num_states for i in range(num_states)] + [0.0]
