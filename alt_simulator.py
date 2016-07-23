# Simulator code for controller test NOT using crowdjs server
# Still using same assignment & aggregation routines as the server
# NOTE use alt_config.json to specify experiment parameters, see README
# NOTE this simulator only supports pomdp assignment+aggregation strategies,
# so alt_config must have the keys 'strategy' and 'aggregation_strategy' set to 'pomdp'

import util
import time
import json
import sys
from controllers.exp_pomdp_controller import expPOMDPController

def debugPrintResp(resp):
    print resp
    print resp.status_code
    print resp.text
    print resp.json()

def setupParams():
    """
    Create params object to pass to simulator. 
    - Makes an API call to get and store the requester's token for later use. 
    - Creates the task on the server, and initializes the worker skills and
      question difficulties that will be used in the simulation.

    See util.py for function implementations, but at the time of this writing:
    - Worker skills are drawn from Normal(1.0, 0.2)
    - Question difficulties are drawn uniformly on [0.0,1.0]
    - Question labels are drawn 50/50 from 0 (False) and 1 (True)

    """
    # Load configuration file 
    params = {}
    with open('alt_config.json') as json_config_file:
        params = json.load(json_config_file)

    start_time_str = time.strftime("%Y_%m_%d_%H_%M_%S")

    # Initialize synthetic workers
    worker_ids = ['w'+str(wi) for wi in range(params['num_workers'])]
    true_skills={w:util.drawWorkerSkill() for w in worker_ids} # given dict mapping w-id to true skill

    # Initialize question labels and difficulties
    question_names = ['q'+str(qi)+'_@_%s' % start_time_str for qi in range(params['num_questions'])]
    true_diffs ={q:util.drawQuestionDifficulty() for q in question_names}# given dict mapping q-name to true difficulty
    true_labels ={q:util.drawRandomLabel() for q in question_names}# given dict mapping q-name to true label

    params['worker_ids'] = worker_ids
    params['question_names'] = question_names
    params['true_skills'] = true_skills
    params['true_diffs'] = true_diffs
    params['true_labels'] = true_labels

    print params
    return params

class Simulator():
    # What to log:
    # - params (ground truth, settings, etc.)
    # - self.votes

    def __init__(self, params):
        #NOTE assumes task+questions already created
        self.params = params
        self.votes = []

        assign_strategy = self.p("strategy")
        agg_strategy = self.p("aggregation_strategy")

        #NOTE Create assignment controller w/strategy+add'l params
        #Create aggregation controller w/agg strategy+add'l params
        if assign_strategy == "pomdp" and agg_strategy == "pomdp":
            settings = self.p("strategy_additional_params")
            settings["worker_ids"] = self.p("worker_ids")
            settings["question_names"] = self.p("question_names")
            self.assignment_controller = expPOMDPController(settings=settings)
            self.aggregation_controller = self.assignment_controller
        else:
            print "Error: strategies not supported", assign_strategy, agg_strategy

    def p(self,key):
        """
        Quick way to get param 'key' from the simulation parameters
        """
        return self.params[key]

    def run_exp(self):
        """
        Given a budget B, get a total of B sequential assignments on the test task
        for our pool of workers.
        
        Assigns questions one worker at a time in sequence,
        looping through the workers until task budget is used up.

        Assumptions:
        - there will always be enough workers to exhaust the budget
          (i.e. we will not get stuck in an infinite loop where no assignments are made)

        """

        # Get workers as a list
        worker_ids = self.p('worker_ids')
        w_idx=0 #first assignment goes to 0th worker
        while len(self.votes) < self.p('budget'):
            print "Budget used so far so far:", len(self.votes)
            # XXX if worker is not assigned to any question, remove from the pool?
            worker_id = worker_ids[w_idx]
            get_resp = self.get_assignment(worker_id)

            if not get_resp.has_key('error'):
                #assignment made

                question_name = get_resp['question_name']

                # simulate worker response
                worker_answer = self.calcResponse(question_name, worker_id)
                value = str(worker_answer['dai_random_response'])
                print("Worker %s response data for question %s: %s" % (worker_id, question_name, str(worker_answer)))

                put_resp = self.put_answer(question_name, worker_id, value)
                self.votes.append((question_name, worker_id, value))

            else:
                # NOTE Assumes error = no assignment, skip this worker
                # XXX could also remove the worker from our pool because
                # they may not necessarily receive future assignments.
                print "Worker %s not given assignment, skipping" % worker_id

            # End of loop; advance to next worker
            w_idx += 1
            if w_idx == len(worker_ids):
                # Back to first worker
                w_idx = 0
    
    def analyze_exp(self, log_file=None):
        json_out = {}
        def json_log_add(k,v):
            """
            Log experiment output as JSON
            """
            print "JSON log adding: " + k + ":" + str(v)
            json_out[k] = v

        # LOG EXPERIMENT PARAMETERS AND RESULTS
        # ----------------------
        # Print parameters
        #XXX do not print auth data for security reasons
        key_blacklist = {'crowdjs_url', 'requester_id', 'auth_token', 'headers'}
        log_params = {}
        for (k,v) in sorted(self.params.iteritems()):
            if k not in key_blacklist:
                log_params[k] = v
        json_log_add("experiment_parameters", log_params) # TODO need json(log_params)?

        # Print votes
        log_votes = []
        for vote in self.votes:
            vote_str = "%s %s %s" % (vote[0], vote[1], vote[2])
            log_votes.append({"question_name":vote[0], "worker_id": vote[1], "label": vote[2]})
        json_log_add("votes", log_votes)

        # Final label stats
        results = self.aggregation_controller.getStatus()

        if self.p('aggregation_strategy') == 'pomdp':
            log_decisions = []
            # Print statistics POMDP decision for each question, 
            # Tally # of correct/incorrect decisions
            # Print number of labels used per question and total
            correct = 0
            for qname in sorted(self.p('question_names')):
                true_label = self.p('true_labels')[qname]
                qid = qname
                pomdp_dec = results[qid]['best_action_str']
                do_submit = "submit"
                true_diff = self.p('true_diffs')[qname]
                votes = [vote for vote in self.votes if vote[0] == qname]
                if pomdp_dec == 'submit-true':
                    dec = 1
                elif pomdp_dec == 'submit-false':
                    dec = 0
                else:
                    # POMDP still wants another label but use its best guess for experiment
                    do_submit = "label!"
                    # see pomdp_peng.py for action indices (currently 0=get another label, 1=submit true, 2=submit false)
                    reward_submit_true = results[qid]['action_rewards']['1']
                    reward_submit_false = results[qid]['action_rewards']['2']
                    if reward_submit_true > reward_submit_false:
                        dec = 1
                    else:
                        dec = 0

                if str(true_label) == str(dec):
                    correct += 1

                log_decisions.append({"question_name":qname, "true_label":true_label, "decision":dec, "do_submit":do_submit, "true_diff":true_diff, "num_labels_q":len(votes)})

            #log
            json_log_add("decisions", log_decisions)
            json_log_add("num_questions_correct", correct)

        # log for all experiments
        json_log_add("num_questions", len(self.p('question_names')))
        json_log_add("num_labels_used", len(self.votes))

        return json_out


    # Utility functions

    def get_assignment(self, worker_id):
        """
        GET an assignment from the server
        """
        assignment = self.assignment_controller.assign([worker_id])
        return {"question_name":assignment[worker_id]}


    def calcResponse(self, question_name, worker_id):
        """
        Simulate worker response to given question using Dai13 accuracy formula
        and the true skill/difficulty/label
        """
        true_label = self.p('true_labels')[question_name]
        true_diff = self.p('true_diffs')[question_name]
        true_skill = self.p('true_skills')[worker_id]
        label = util.calcResponse(true_label, true_diff, true_skill)
        accuracy = util.calcAccuracy(true_skill, true_diff)
        data = {"true_label": true_label,
                "true_diff": true_diff,
                "true_skill": true_skill,
                "dai_random_response": label,
                "accuracy": accuracy}
        return data

    def put_answer(self, question_name, worker_platform_id, value):
        """
        PUT (upload) worker answer to server

        """
        data = {
#               "requester_id" : self.p('requester_id'),
#               "task_id" : self.p('task_id'),
                "question_name" : question_name,
                "worker_id" : worker_platform_id,
#               "worker_source" : self.p('worker_source'),
                "value" : value}
        return self.assignment_controller.addObservation(data)

if __name__ == '__main__':
    out_file = open(sys.argv[1], 'w')
    params = setupParams()
    sim = Simulator(params)
    sim.run_exp()
    json_log = sim.analyze_exp()
    print "JSON log:"
    #TODO write to output file
    print(json.dumps(json_log, sort_keys=True, indent=4))
    json.dump(json_log, out_file, sort_keys=True, indent=4)
