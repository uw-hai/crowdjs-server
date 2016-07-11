#simulator code for end-to-end controller test
#NOTE worker_id should refer to worker_platform_id in all cases

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
    #create params object to pass to simulator
    params={}

    # XXX important experiment setup
    #Strategies for assignment & aggregation
    params['strategy'] = 'pomdp' # for assignment='min_answers' 'random' or 'pomdp'
    params['aggregation_strategy'] = 'pomdp' # for aggregation='majority_vote' 'EM' or 'pomdp' 

    NUM_WORKERS = 10
    NUM_QUESTIONS = 5
    params['budget'] = 3*NUM_QUESTIONS

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




    #initialize synthetic workers
    worker_ids = ['w'+str(wi) for wi in range(NUM_WORKERS)]
    true_skills={w:util.drawWorkerSkill() for w in worker_ids} # given dict mapping w-id to true skill

    #initialize question label+diff
    question_names = ['q'+str(qi)+' @ %s' % start_time_str for qi in range(NUM_QUESTIONS)]
    true_diffs ={q:util.drawQuestionDifficulty() for q in question_names}# given dict mapping q-name to true difficulty
    true_labels ={q:util.drawRandomLabel() for q in question_names}# given dict mapping q-name to true label

    #create task object
    #json questions to upload within task
    question_objs = [{'requester_id': requester_id,
                      'question_name': q,
                      'question_description': 'test question desc'} 
                 for q in question_names]
    task_obj = {'requester_id': requester_id,
            'task_name': 'simulator test task @ %s' % start_time_str,
            'task_description': 'test task desc',
            'questions': question_objs,
            'answers_per_question': 99}


    #upload task+questions to DB
    resp=requests.put(crowdjs_url+'/tasks', headers=headers, json=task_obj)
    debugPrintResp(resp)
    task_id = resp.json()['task_id']
    question_ids = resp.json()['question_ids']

    #mapping Question names <-> ids
    params['question_names_to_ids'] = {}
    params['question_ids_to_names'] = {}
    for i in range(NUM_QUESTIONS):
        q_name = question_names[i]
        q_id = question_ids[i]
        params['question_names_to_ids'][q_name] = q_id
        params['question_ids_to_names'][q_id] = q_name



    #not fixed things to add to param
    params['crowdjs_url'] = crowdjs_url
    params['requester_id'] = requester_id
    params['auth_token'] = auth_token
    params['task_id'] = task_id
    params['headers'] = headers

    #Keep these around
    params['task_obj'] = task_obj
    params['worker_ids'] = worker_ids
    params['question_names'] = question_names

    params['true_skills'] = true_skills
    params['true_diffs'] = true_diffs
    params['true_labels'] = true_labels

    #fixed things to add to params
    params['assignment_get_endpoint'] = "/assign_next_question"
    params['answer_put_endpoint'] = "/answers"
    params['worker_source'] = 'mturk'



    print params
    return params

class Simulator():
    def __init__(self, params):
        #assumes task+questions already created
        self.params = params
        self.votes = []

    def p(self,key):
        """Get parameter 'key'
        """
        #XXX the most convenient way to store all this stuff and look it up?
        return self.params[key]

    def run_exp(self):
        #get workers as a list
        worker_ids = self.p('worker_ids')
        w_idx=0 #first assignment goes to 0th worker
        budget_used = 0
        while budget_used < self.p('budget'):
            print "# votes so far:", len(self.votes)
            # Assign questions one worker at a time,
            # loop through workers until task complete.
            # Assumes there will always be enough workers to complete the task
            # with the desired # of labels
            # TODO if worker is not assigned to any question, remove from the pool?
            worker_id = worker_ids[w_idx]
            get_resp = self.get_assignment(worker_id)

            if not get_resp.has_key('error'):
                #assignment made

                question_name = get_resp['question_name']

                # simulate worker response
                value, accuracy = self.calcResponse(question_name, worker_id)
                print "accuracy = "
                value = str(value)
                print("worker %s response to question %s = %s" % (worker_id, question_name, value))

                put_resp = self.put_answer(question_name, worker_id, value)
                self.votes.append((question_name, worker_id, value))

                budget_used += 1
            else:
                #NOTE if json = error no assignment, skip worker
                print "Worker %s not given assignment, skipping" % worker_id

            # end of loop increments
            w_idx += 1
            if w_idx == len(worker_ids):
                #reset to first worker
                w_idx = 0

        # Experiment results
        self.analyze_exp()
    
    def analyze_exp(self):
        # TODO decide whether to just log everything during run_exp or pull results from DB after
        # want to keep the server as a black box

        # NOTE run an EM job for reference
        data = {"requester_id": self.p('requester_id'),
                "strategy": "EM"} 

        em_resp = requests.put(self.p('crowdjs_url') + '/tasks/%s/aggregate' % self.p('task_id'), headers = self.p('headers'), json=data)
        em_job_id = em_resp.json()['_id']['$oid']
        print "inference job_id = ", em_job_id
        em_dataGET = {"requester_id": self.p('requester_id')}

        #Get EM results
        em_get_resp = requests.get(self.p('crowdjs_url') + '/tasks/%s/aggregate/%s' % (self.p('task_id'), em_job_id), headers = self.p('headers'), json=em_dataGET)
        print em_get_resp.json()['results']


        # Get decision for each question from the server
        # TaskAggregationAPI needs to support MV and POMDP strategies, run an InferenceJob for each
        data = {"requester_id": self.p('requester_id'),
                "strategy": self.p('aggregation_strategy')} #majority_vote, EM, or POMDP
        resp = requests.put(self.p('crowdjs_url') + '/tasks/%s/aggregate' % self.p('task_id'), headers = self.p('headers'), json=data)
        job_id = resp.json()['_id']['$oid']
        print "inference job_id = ", job_id
        dataGET = {"requester_id": self.p('requester_id')}

        #Get POMDP status
        ij_resp = requests.get(self.p('crowdjs_url') + '/tasks/%s/aggregate/%s' % (self.p('task_id'), job_id), headers = self.p('headers'), json=dataGET)

        # POMDP self.policy.get_action_rewards for each question, return that w/readable best action (i.e. submit-true, submit-false)
        print ij_resp.json()
        print "POMDP status Results:"
        results = ij_resp.json()['results']
        for (q,res) in results.iteritems():
            print q, res


        # TODO Count number of labels used
        # Tally # of accurate 'submit' questions
        # Tally # of would-be accurate questions but pomdp wants another label
        # Tally # of wrong answers
        
        print "----------------"
        print "Names->IDs mapping:", self.p('question_names_to_ids')

        correct = 0
        for qname in self.p('question_names'):
            true_label = self.p('true_labels')[qname]
            qid = self.p("question_names_to_ids")[qname]
            pomdp_dec = results[qid]['best_action_str']
            votes = [vote for vote in self.votes if vote[0] == qname]
            if pomdp_dec == 'submit-true':
                dec = 1
            elif pomdp_dec == 'submit-false':
                dec = 0

            if true_label == dec:
                correct += 1
            print true_label, pomdp_dec, len(votes)
        print "%d out of %d questions correct" % (correct, len(self.p('question_names')))

    def get_assignment(self, worker_id):
        """
        Get an assignment from the server
        """
        data = {"worker_id": worker_id,
                "worker_source": self.p('worker_source'),
                "task_id": self.p('task_id'),
                "requester_id": self.p('requester_id'),
                "strategy": self.p('strategy')}

        print("getting assignment data = " + str(data))
        resp = requests.get(self.p('crowdjs_url') + self.p('assignment_get_endpoint'), headers = self.p('headers'), json=data)
        debugPrintResp(resp)
        return resp.json()

    def calcResponse(self, question_name, worker_platform_id):
        """
        Simulate worker response to given question using Dai13 accuracy formula
        and the true skill/difficulty/label
        """
        true_label = self.p('true_labels')[question_name]
        true_diff = self.p('true_diffs')[question_name]
        true_skill = self.p('true_skills')[worker_platform_id]
        label = util.calcResponse(true_label, true_diff, true_skill)
        accuracy = util.calcAccuracy(true_skill, true_diff)
        data = {"true_label": true_label,
                "true_diff": true_diff,
                "true_skill": true_skill,
                "dai_random_response": label,
                "accuracy": accuracy}
        #TODO log responses if needed
        print data
        return label, accuracy

    def put_answer(self, question_name, worker_platform_id, value):
        """
        Upload worker answer to server

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
