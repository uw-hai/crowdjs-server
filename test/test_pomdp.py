import unittest
import pomdp
import pomdp_peng

class TigerPOMDP(object):
    """Test POMDP model with hard-coded probabilities."""
    def __init__(self):
        self.states = ['left', 'right']
        self.actions = ['listen', 'open-left', 'open-right']
        self.observations = ['left', 'right']

    @staticmethod
    def f_start(s):
        return 0.5

    @staticmethod
    def f_reward(s, a, s1):
        if (s == 'left' and a == 'open-left' or
            s == 'right' and a == 'open-right'):
            return 2
        elif a == 'listen':
            return -0.1
        else:
            return -10

    @staticmethod
    def f_observation(s, a, o):
        if a == 'listen' and s == o:
            return 0.7
        elif a == 'listen':
            return 0.3
        else:
            return 0.5

    @staticmethod
    def f_transition(s, a, s1):
        # NOTE: Tiger never moves.
        if s == s1:
            return 1
        else:
            return 0

class POMDPTestCase(unittest.TestCase):
    def setUp(self):
        self.pomdp = TigerPOMDP()

    def test_solve(self):
        # TODO: Check returned policy.
        zpomdp = pomdp.ZPOMDP()
        policy = zpomdp.solve(
            self.pomdp.states, self.pomdp.actions, self.pomdp.observations,
            self.pomdp.f_start, self.pomdp.f_transition,
            self.pomdp.f_observation, self.pomdp.f_reward,
            discount=0.75, timeout=60)
        print policy
        belief = [0.5,0.5]
        print policy.get_best_action(belief)

    def test_peng_pomdp(self):
        zpomdp = pomdp.ZPOMDP()
        # discretize difficulty into n bins, set avg worker gamma
        peng_pomdp = pomdp_peng.PengPOMDP(5, 1.0)
        policy = zpomdp.solve(
                peng_pomdp.states, peng_pomdp.actions, peng_pomdp.observations,
                peng_pomdp.CLOSURE_f_start(len(peng_pomdp.states)), peng_pomdp.f_transition,
                peng_pomdp.CLOSURE_f_observation(peng_pomdp.avg_worker_skill), peng_pomdp.f_reward,
                discount=0.99, timeout=120)

        import numpy as np
        np.set_printoptions(suppress=True)
        print policy
        #TODO belief = ???
        for i in policy.pMatrix:
            print i
#           for j in i:
#               print j

        belief = [0.0 for i in range(len(peng_pomdp.states))]
        i = 7 # odd
        print peng_pomdp.states[i]
        belief[i] = 0.96 #fairly easy question
        belief[i+1] = 0.04
        
        #XXX set belief uniform over all non-terminal states
        #belief = [1.0/len(peng_pomdp.states) for i in range(len(peng_pomdp.states))]
        #belief = [2.0/len(peng_pomdp.states) if not get_state(s)[2] else 0 for s in peng_pomdp.states]
        belief = [1.0/(len(peng_pomdp.states)-1) if not pomdp_peng.is_terminal_state(s) else 0.0 for s in peng_pomdp.states]

        #
        print "belief =",belief
        print "best action, expected reward = ", policy.get_best_action(belief)
        raw_input()

if __name__ == '__main__':
    unittest.main()
