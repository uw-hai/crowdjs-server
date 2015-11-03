"""pomdp.py"""

import os
import subprocess
import tempfile
import shutil
import pomdp_policy

class POMDP(object):
    """Base POMDP class."""
    def __init__(self):
        raise NotImplementedError

    def solve(self, model):
        """Return parsed policy."""
        raise NotImplementedError

    def write_cassandra(self, fo, states, actions, observations, f_start,
                        f_transition, f_observation, f_reward, discount):
        """Write a Cassandra-style POMDP file."""
        if discount >= 1.0:
            raise Exception('Discount must be less than 1.0')

        # Write header
        fo.write('discount: {}\n'.format(discount))
        fo.write('values: reward\n')
        fo.write('states: {}\n'.format(' '.join(str(s) for s in states)))
        fo.write('actions: {}\n'.format(' '.join(str(a) for a in actions)))
        fo.write('observations: {}\n'.format(' '.join(observations)))

        fo.write('start: {}\n'.format(' '.join(str(f_start(s)) for
                                               s in states)))

        fo.write('\n\n### Transitions\n')
        for s in states:
            for a in actions:
                for s1 in states:
                    fo.write('T: {} : {} : {} {}\n'.format(
                        a, s, s1, f_transition(s, a, s1)))
                fo.write('\n')

        fo.write('\n\n### Observations\n')
        for s in states:
            for a in actions:
                for o in observations:
                    fo.write('O: {} : {} : {} {}\n'.format(
                        a, s, o, f_observation(s, a, o)))
                fo.write('\n')

        fo.write('\n\n### Rewards\n')
        for s in states:
            for a in actions:
                for s1 in states:
                    fo.write('R: {} : {} : {} : * {}\n'.format(
                        a, s, s1, f_reward(s, a, s1)))
                fo.write('\n')


class ZPOMDP(POMDP):
    """ZMDP POMDP class."""
    def __init__(self):
        pass

    def solve(self, states, actions, observations, f_start, f_transition,
              f_observation, f_reward, discount, timeout=None):
        # TODO(jbragg): Parse policy output and return object before
        # deleting directory.
        d = tempfile.mkdtemp()
        model_filename = os.path.join(d, 'm.pomdp')
        policy_filename = os.path.join(d, 'p.policy')
        with open(model_filename, 'w') as f:
            self.write_cassandra(
                f, states, actions, observations, f_start,
                f_transition, f_observation, f_reward, discount)
        args = [os.environ['ZMDP_ALIAS'], 'solve', model_filename,
                '-o', policy_filename]
        if timeout:
            args += ['-t', str(timeout)]

        exit_status = subprocess.call(args)

        # NOTE check that solver ran successfully
        assert exit_status == 0

        # parse policy output
        policy = pomdp_policy.POMDPPolicy(policy_filename, file_format='zmdp', n_states=len(states))

        shutil.rmtree(d)
        return policy
