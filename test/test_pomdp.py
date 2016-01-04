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
            discount=0.95, timeout=60)
        belief = [0.5,0.5]

        action, reward = policy.get_best_action(belief)

        print policy
        print action, reward


        # TODO solve this POMDP + belief state
#       expected_action = 0
#       expected_reward = ???
#       self.assertEqual(expected_action, action)
#       self.assertAlmostEqual(expected_reward, reward)

    def test_peng_pomdp(self):
        zpomdp = pomdp.ZPOMDP()
        # discretize difficulty into n bins, set avg worker gamma
        peng_pomdp = pomdp_peng.PengPOMDP(11, 0.5)
        policy = zpomdp.solve(
                peng_pomdp.states, peng_pomdp.actions, peng_pomdp.observations,
                peng_pomdp.CLOSURE_f_start(len(peng_pomdp.states)), peng_pomdp.f_transition,
                peng_pomdp.CLOSURE_f_observation(peng_pomdp.avg_worker_skill), peng_pomdp.CLOSURE_f_reward(create=-1,correct=0,incorrect=-10),
                discount=0.9999, timeout=300)

        import numpy as np
        np.set_printoptions(suppress=True)
        print policy
        for i in policy.pMatrix:
            print i

        # NOTE tests a few different belief states and checks the resulting actions/expected rewards
        # XXX Assumes -1,+0,-10 rewards (get another label, correct, incorrect)


        # Easy test: fix answer = true (difficulty doesn't matter)
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        belief[0] = 0.7
        belief[1] = 0.3
        expected_action = 1 # submit true
        expected_reward = 0.0 # when reward_correct=1, 1.0
        action, reward = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward
        self.assertEqual(expected_action, action)
        self.assertAlmostEqual(expected_reward, reward)

        # Easiest difficulty, 95% chance of being true
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        belief[0] = 0.95
        belief[11] = 0.05
        expected_action = 1 # submit true
        expected_reward = -0.5 # when reward_correct=1, 0.45
        action, reward = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward
        self.assertEqual(expected_action, action)
        self.assertAlmostEqual(expected_reward, reward)

        # Fixed difficulty=0, <90% chance true
        # should get another label
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        i=0
        belief[i] = 0.8999
        belief[i+11] = 1-belief[i]
        expected_action = 0 # get another label
        expected_reward = -1.0 # NOTE total reward must be < -1 (for discount > 0). reward-correct=1->-0.001
        action, reward = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward
        self.assertEqual(expected_action, action)
        self.assertAlmostEqual(expected_reward, reward)

        # Fixed difficulty=0.1, <90% chance true
        # should get another label
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        i=1
        belief[i] = 0.8
        belief[i+11] = 1-belief[i]
        expected_action = 0 # get another label
        expected_reward = -1.0 # NOTE total reward must be < -1 (for discount > 0). reward-correct=1->-0.001
        action, reward_point1 = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward_point1
        self.assertEqual(expected_action, action)
        self.assertGreater(expected_reward, reward_point1)

        # Fixed difficulty=0.2, <90% chance true
        # should get another label
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        i=2
        belief[i] = 0.8
        belief[i+11] = 1-belief[i]
        expected_action = 0 # get another label
        expected_reward = -1.0 # TODO better bound
        action, reward_point2 = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward_point2
        self.assertEqual(expected_action, action)
        self.assertGreater(expected_reward, reward_point2)

        #NOTE expected reward should be worse when difficulty is higher
        self.assertGreater(reward_point1, reward_point2)
        
        # NOTE belief = uniform over all difficulties, answers
        NS = len(peng_pomdp.states)-1 # number of non-terminal states
        belief = [1.0/NS for i in range(NS)] + [0.0]
        expected_action = 0 # get another label
        expected_reward = -2 # reward=1 -> -1.9473589090909...
        action, reward = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward
        self.assertEqual(expected_action, action)
        self.assertGreater(expected_reward, reward)

        # Fixed difficulty=1.0, >50% chance true
        # 1st worker should just guess true - getting another label won't help!
        belief = [0.0 for i in range(len(peng_pomdp.states))]
        i=10
        belief[i] = 0.5001
        belief[i+11] = 1-belief[i]
        expected_action = 1 # submit true
        expected_reward = -4.999 # NOTE worker skill has no effect, so 50/50 answering either way
        action, reward = policy.get_best_action(belief)
        print belief
        print expected_action, expected_reward
        print action, reward
        self.assertEqual(expected_action, action)
        self.assertAlmostEqual(expected_reward, reward)

        #XXX set belief uniform over all non-terminal states
        #belief = [1.0/len(peng_pomdp.states) for i in range(len(peng_pomdp.states))]
        #belief = [2.0/len(peng_pomdp.states) if not get_state(s)[2] else 0 for s in peng_pomdp.states]
        belief = [1.0/(len(peng_pomdp.states)-1) if not pomdp_peng.is_terminal_state(s) else 0.0 for s in peng_pomdp.states]

        #TODO finish test
        print "belief =",belief
        print "best action, expected reward = ", policy.get_best_action(belief)

if __name__ == '__main__':
    unittest.main()
