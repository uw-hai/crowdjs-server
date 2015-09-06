import unittest
import pomdp

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
        zpomdp.solve(
            self.pomdp.states, self.pomdp.actions, self.pomdp.observations,
            self.pomdp.f_start, self.pomdp.f_transition,
            self.pomdp.f_observation, self.pomdp.f_reward,
            discount=0.99, timeout=60)

if __name__ == '__main__':
    unittest.main()
