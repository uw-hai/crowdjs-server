"""
Dai et al POMDP from aij paper.
"""
import itertools

TERMINAL_STATE = "TERMINAL-STATE"

def is_terminal_state(s):
    return s == TERMINAL_STATE

def get_state(state_string):
    """Helper for Peng POMDP because Cassandra format doesn't work w/ (d,v) state pairs"""
    if state_string == TERMINAL_STATE:
        return TERMINAL_STATE
    s = state_string.split("---")[1:]
    d = float(s[0].replace("point","."))
    v = True if s[1] == 'True' else False
#   submitted = True if s[2] == 'True' else False
    return (d,v)
#   return (d,v,submitted)

#def make_state(d,v,submitted):
#    return "d-v---" + str(d).replace(".","point") + "---" + str(v) + "---" + str(submitted)

def make_state(d,v):
    return "d-v---" + str(d).replace(".","point") + "---" + str(v)


class PengPOMDP(object):
    def __init__(self, num_diff_bins, avg_worker_skill):
        """
        from paper:
        states = {(d,v) | d \in [0,1], v \in {0,1}}
        We add an additional terminal state, entered upon answer submission.
        --
        num_diff_bins = discretize [0,1] into n bins
        i.e. 11 bins = [0, 0.1, ..., 1]
        """
        bins = [float(i)/(num_diff_bins-1) for i in range(num_diff_bins)]
        answers = ['True', 'False']
        #NOTE additional terminal state - don't forget when computing probabilities
        self.states = [TERMINAL_STATE] + [make_state(d,v) for d,v in itertools.product(bins, answers)]
        self.actions = ['create-another-job', 'submit-true', 'submit-false']
        self.observations = ['True', 'False']
        self.avg_worker_skill = avg_worker_skill

    @staticmethod
    def CLOSURE_f_start(num_states):
        #NOTE assumes label prior = 0.5, difficulty prior = uniform over bins
        def f_start(s):
            if is_terminal_state(s):
                return 0.0
            else:
                return 1.0/(num_states-1)
        return f_start

    @staticmethod
    def f_reward(s, a, s1):
        if is_terminal_state(s):
            return 0

        d,v = get_state(s)
        if a == 'create-another-job':
            return -1
        elif (a == 'submit-true' and v == True
                or a == 'submit-false' and v == False):
            # Correct answer
            return 0
        else:
            # Incorrect answer
            return -10

    @staticmethod
    def CLOSURE_f_observation(gamma):
        def f_observation(s, a, o):

            #TODO do we care about obs in terminal state?
            #BUG just return 1/0 for now so the math works
            if is_terminal_state(s):
                if o == 'True':
                    return 1.0
                else:
                    return 0.0

            d,v = get_state(s)
            o = True if o == 'True' else False
            #a(d,gamma) = 0.5*(1+(1-d)^gamma)
            #P(o = v|d) = a(d,gamma)
            P_correct = 0.5*(1+(1-d)**gamma)
            if o == v:
                return P_correct
            else:
                return 1-P_correct
        return f_observation


    @staticmethod
    def f_transition(s, a, s1):
        #TODO cleanup
        if is_terminal_state(s) and is_terminal_state(s1):
            #stay in terminal state
            return 1
        elif is_terminal_state(s):
            return 0

        if (a == 'submit-true' or a == 'submit-false') and is_terminal_state(s1):
            #submitting => goes to terminal state
            return 1
        elif s == s1 and a == 'create-another-job':
            #not submitting => stay in same state
            return 1
        else:
            return 0


