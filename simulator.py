# Simulator code for end-to-end controller test
# NOTE requires a separate config.json file, see README
# NOTE worker_id refers to worker_platform_id in all cases, not the DB worker id

import requests
import util
import time
import json

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

    """
    params={}

    # Choose experiment number of questions & workers and fix a budget
    #TODO allow passing in from command line
    NUM_WORKERS = 10
    NUM_QUESTIONS = 5
    AVG_BUDGET_PER_QUESTION = 1
    # NOTE Simple budget for early experiments (to compare to fixed allocation of labels)
    params['budget'] = AVG_BUDGET_PER_QUESTION*NUM_QUESTIONS
    params['strategy'] = 'pomdp' # for assignment='min_answers' 'random' or 'pomdp'
    params['strategy_additional_params'] = {'reward_incorrect': '-28'}
    params['aggregation_strategy'] = 'pomdp' # for aggregation='majority_vote' 'EM' or 'pomdp' 
    params['aggregation_strategy_additional_params'] = {'reward_incorrect': '-29'}

    # Load configuration file
    with open('config.json') as json_config_file:
        config = json.load(json_config_file)

    crowdjs_url = config['crowdjs_url']
    email = config['test_requester_email']
    password = config['test_requester_password']

    # Get requester's ID and API token
    r = requests.get(crowdjs_url + '/token', auth=(email, password))
    data = r.json()
    requester_id = data['requester_id']
    auth_token = data['auth_token']

    headers = {"Authentication-Token": auth_token,
               "Content-Type": "application/json"} 

    start_time_str = time.strftime("%Y_%m_%d_%H_%M_%S")

    # Initialize synthetic workers
    worker_ids = ['w'+str(wi) for wi in range(NUM_WORKERS)]
    true_skills={w:util.drawWorkerSkill() for w in worker_ids} # given dict mapping w-id to true skill

    # Initialize question labels and difficulties
    question_names = ['q'+str(qi)+' @ %s' % start_time_str for qi in range(NUM_QUESTIONS)]
    true_diffs ={q:util.drawQuestionDifficulty() for q in question_names}# given dict mapping q-name to true difficulty
    true_labels ={q:util.drawRandomLabel() for q in question_names}# given dict mapping q-name to true label

    # Create task object containing the questions
    question_objs = [{'requester_id': requester_id,
                      'question_name': q,
                      'question_description': 'test question desc'} 
                 for q in question_names]
    task_obj = {'requester_id': requester_id,
            'task_name': 'simulator test task @ %s' % start_time_str,
            'task_description': 'test task desc',
            'questions': question_objs,
            'answers_per_question': 99}


    # Upload task+questions to DB
    resp=requests.put(crowdjs_url+'/tasks', headers=headers, json=task_obj)
    debugPrintResp(resp)
    task_id = resp.json()['task_id']
    question_ids = resp.json()['question_ids']

    # Setup mapping from Question names <-> ids
    params['question_names_to_ids'] = {}
    params['question_ids_to_names'] = {}
    for i in range(NUM_QUESTIONS):
        q_name = question_names[i]
        q_id = question_ids[i]
        params['question_names_to_ids'][q_name] = q_id
        params['question_ids_to_names'][q_id] = q_name

    # Server parameters
    params['crowdjs_url'] = crowdjs_url
    params['requester_id'] = requester_id
    params['auth_token'] = auth_token
    params['headers'] = headers

    # Lists of task questions and worker stats to use later
    params['task_id'] = task_id
    params['task_obj'] = task_obj
    params['worker_ids'] = worker_ids
    params['question_names'] = question_names
    params['true_skills'] = true_skills
    params['true_diffs'] = true_diffs
    params['true_labels'] = true_labels

    # Server API details
    params['assignment_get_endpoint'] = "/assign_next_question"
    params['answer_put_endpoint'] = "/answers"
    params['worker_source'] = 'mturk'

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
        def exp_log(string):
            """
            Log experiment output to file
            """
            print string
            if log_file is not None:
                log_file.write(string + '\n')
#       # NOTE run an EM job for reference
#       data = {"requester_id": self.p('requester_id'),
#               "strategy": "EM"} 

#       em_resp = requests.put(self.p('crowdjs_url') + '/tasks/%s/aggregate' % self.p('task_id'), headers = self.p('headers'), json=data)
#       em_job_id = em_resp.json()['_id']['$oid']
#       print "inference job_id = ", em_job_id
#       em_dataGET = {"requester_id": self.p('requester_id')}

#       #Get EM results
#       em_get_resp = requests.get(self.p('crowdjs_url') + '/tasks/%s/aggregate/%s' % (self.p('task_id'), em_job_id), headers = self.p('headers'), json=em_dataGET)
#       print em_get_resp.json()['results']

#       print "----------------"
        print "Question names->IDs mapping:", self.p('question_names_to_ids')

        # Get decision for each question from the server
        data = {"requester_id": self.p('requester_id'),
                "strategy": self.p('aggregation_strategy'),
                "additional_params": self.p("aggregation_strategy_additional_params")} #majority_vote, EM, or POMDP
        resp = requests.put(self.p('crowdjs_url') + '/tasks/%s/aggregate' % self.p('task_id'), headers = self.p('headers'), json=data)
        job_id = resp.json()['_id']['$oid']
        print "inference job_id = ", job_id
        dataGET = {"requester_id": self.p('requester_id')}
        ij_resp = requests.get(self.p('crowdjs_url') + '/tasks/%s/aggregate/%s' % (self.p('task_id'), job_id), headers = self.p('headers'), json=dataGET)
        results = ij_resp.json()['results']
        print "Inference job results:"
        for (q,res) in results.iteritems():
            print q, res

        print "----------------"

        # LOG EXPERIMENT PARAMETERS AND RESULTS
        # ----------------------
        # Print parameters
        #XXX do not print auth data for security reasons
        exp_log("Experiment parameters:")
        key_blacklist = {'crowdjs_url', 'requester_id', 'auth_token', 'headers'}
        for (k,v) in sorted(self.params.iteritems()):
            if k not in key_blacklist:
                exp_log("%s: %s" % (str(k),str(v)))

        # Print votes
        exp_log("Vote format: qname, worker_id, label")
        for vote in self.votes:
            vote_str = "%s %s %s" % (vote[0], vote[1], vote[2])
            exp_log(vote_str)

        if self.p('strategy') == 'pomdp':
            # Print statistics POMDP decision for each question, 
            # Tally # of correct/incorrect decisions
            # Print number of labels used per question and total
            exp_log("POMDP decisions:")
            exp_log("Columns: qname, true_label (0/1), pomdp_decision (0/1/-1), question_difficulty, num_labels_used")
            correct = 0
            for qname in self.p('question_names'):
                true_label = self.p('true_labels')[qname]
                qid = self.p("question_names_to_ids")[qname]
                pomdp_dec = results[qid]['best_action_str']
                do_submit = True
                true_diff = self.p('true_diffs')[qname]
                votes = [vote for vote in self.votes if vote[0] == qname]
                if pomdp_dec == 'submit-true':
                    dec = 1
                elif pomdp_dec == 'submit-false':
                    dec = 0
                else:
                    # POMDP still wants another label but use its best guess for experiment
                    do_submit = False
                    # see pomdp_peng.py for action indices (currently 0=get another label, 1=submit true, 2=submit false)
                    reward_submit_true = results[qid]['action_rewards']['1']
                    reward_submit_false = results[qid]['action_rewards']['2']
                    if reward_submit_true > reward_submit_false:
                        dec = 1
                    else:
                        dec = 0

                if true_label == dec:
                    correct += 1

                exp_log("%s %d %d %s %.2f %d" % (qname, true_label, dec, str(do_submit), true_diff, len(votes)))
            exp_log("%d out of %d questions correct" % (correct, len(self.p('question_names'))))
            exp_log("Used %d labels in total" % len(self.votes))


    # Utility functions

#   def exp_log(self, string):
#       """
#       Log experiment output to file
#       """
#       #TODO write to file
#       print string

    def get_assignment(self, worker_id):
        """
        GET an assignment from the server
        """
        data = {"worker_id": worker_id,
                "worker_source": self.p('worker_source'),
                "task_id": self.p('task_id'),
                "requester_id": self.p('requester_id'),
                "strategy": self.p('strategy'),
                "additional_params": self.p('strategy_additional_params')}

        print("getting assignment data = " + str(data))
        resp = requests.get(self.p('crowdjs_url') + self.p('assignment_get_endpoint'), headers = self.p('headers'), json=data)
        debugPrintResp(resp)
        return resp.json()

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
        data = {"requester_id" : self.p('requester_id'),
                "task_id" : self.p('task_id'),
                "question_name" : question_name,
                "worker_id" : worker_platform_id,
                "worker_source" : self.p('worker_source'),
                "value" : value}

        print("Putting answer data = " + str(data))

        resp = requests.put(self.p('crowdjs_url') + self.p('answer_put_endpoint'), headers=self.p('headers'), json=data)
        debugPrintResp(resp)
        return resp.json()

if __name__ == '__main__':
    params = setupParams()
    sim = Simulator(params)
    sim.run_exp()
    sim.analyze_exp()
