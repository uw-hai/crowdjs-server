from __future__ import division
import numpy as np
import zmdp_util
import random

class POMDPPolicy:
    '''
    Based on mbforbes/py-pomdp on github.

    Read a policy file

    Attributes:
        action_nums    The full list of action (numbers) from the alpha
                       vectors. In other words, this saves the action
                       number from each alpha vector and nothing else,
                       but in the order of the alpha vectors.

        pMatrix        The policy matrix, constructed from all of the
                       alpha vectors.
    '''
    def __init__(self, filename, file_format='policyx', n_states=None):
        self.file_format = file_format
        if file_format == 'policyx':
            tree = ee.parse(filename)
            root = tree.getroot()
            avec = list(root)[0]
            alphas = list(avec)
            self.action_nums = []
            val_arrs = []
            for alpha in alphas:
                self.action_nums.append(int(alpha.attrib['action']))
                vals = []
                for val in alpha.text.split():
                    vals.append(float(val))
                val_arrs.append(vals)
            if len(val_arrs) == 0:
                raise Exception('APPL policy contained no alpha vectors')
            self.pMatrix = np.array(val_arrs)
        elif file_format == 'aitoolbox':
            # Retrieve max horizon alpha vectors.
            # TODO: Allow retrieval of horizons other than max.
            horizons = [[]]
            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('@'):
                        horizons.append([])
                    else:
                        horizons[-1].append(line)
            horizons = [lst for lst in horizons if len(lst) > 0]
            if len(horizons) == 0:
                raise Exception('AIToolbox policy contained no alpha vectors')
            lines_max_horizon = horizons[-1]
            alphas = [[float(v) for v in line.split()[:n_states]] for
                      line in lines_max_horizon]
            self.pMatrix = np.array(alphas)
            self.action_nums = [int(line.split()[n_states]) for
                                line in lines_max_horizon]
        elif file_format == 'zmdp':
            actions, alphas = zmdp_util.read_zmdp_policy(filename, n_states)
            self.action_nums = actions
            self.pMatrix = np.array(alphas)
        else:
            raise NotImplementedError

    def __repr__(self):
        return "pMatrix: " + str(self.pMatrix) + "\naction_nums: " + str(self.action_nums)

    def zmdp_filter(self, belief, alpha):
        """Return true iff this alpha vector applies to this belief"""
        return not any(b > 0 and a is None for b,a in zip(belief, alpha))

    def zmdp_convert(self, alpha):
        """Return new array with Nones replaced with 0's"""
        return [a if a is not None else 0 for a in alpha]

    def get_best_action(self, belief):
        '''
        Returns tuple:
            (best-action-num, expected-reward-for-this-action).
        '''
        """
        res = self.pMatrix.dot(belief)
        highest_expected_reward = res.max()
        best_action = self.action_nums[res.argmax()]
        return (best_action, highest_expected_reward)
        """
        #raise NotImplementedError # Untested.
        res = self.get_action_rewards(belief)
        max_reward = max(res.itervalues())
        best_action = random.choice([a for a in res if res[a] == max_reward])
        return (best_action, max_reward)


    def get_action_rewards(self, belief):
        '''
        Returns dictionary:
            action-num: max expected-reward.
        '''
        if self.file_format == 'zmdp':
            alpha_indices_relevant = [
                i for i,alpha in enumerate(self.pMatrix) if
                self.zmdp_filter(belief, alpha)]
            alphas = []
            actions = []
            for i in alpha_indices_relevant:
                alphas.append(self.zmdp_convert(self.pMatrix[i,:]))
                actions.append(self.action_nums[i])
            alphas = np.array(alphas)
        else:
            alphas = self.pMatrix
            actions = self.action_nums
        res = alphas.dot(belief)
        d = dict()
        for a,r in zip(actions, res):
            if a not in d:
                d[a] = r
            else:
                d[a] = max(d[a], r)
        return d
