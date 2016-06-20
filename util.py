import numpy as np


def majorityVote(ballot):
    """
    Returns (value, count) tuple. Tiebreaking behavior not specified
    """
    from collections import Counter
    data = Counter(ballot)
    maj_vote = data.most_common(1)[0]
    return maj_vote


def calcResponse(true_answer, d, gamma):
    # based on Dai accuracy
    # have to know true answer
    # a(d,g) = 0.5*(1+(1-d)^g)

    # P(bw = v|d) = a(d,g)
    p_correct = 0.5 * (1 + (1 - d)**gamma)
    if np.random.random() <= p_correct:
        # answer correctly
        resp = true_answer
    else:
        # answer incorrectly
        resp = 1 - true_answer

    return resp


def drawQuestionDifficulty():
    return np.random.random()


def drawWorkerSkill():
    # assign worker skill
    # draw from Normal(1.0, 0.2)
    gamma = np.random.normal(1.0, 0.2)
    return gamma

def drawRandomLabel(possible_labels=[0,1]):
    # choose random label uniformly
    return np.random.choice(possible_labels)


def calcAccuracy(gamma, d):
    return (1.0 / 2) * (1.0 + (1.0 - d) ** gamma)


def normalize(array):
    sum = 0.0
    for i in range(0, len(array)):
        sum += array[i]
    for i in range(0, len(array)):
        array[i] = array[i] / sum
    return array


# Dai/AIJ13 pomdp question belief definitions

def initBelief(numLabelChoices, numDifficulties):
    """Initialize question belief state over the possible answers and difficulty bins.
    
    Uniform over each (label, difficulty) pair and also appends p=0.0 of being 
    in the terminal (already submitted) state, so returns a C*D+1 length list.
    """
    num_nonterminal_states = numDifficulties * numLabelChoices
    return [1.0/num_nonterminal_states for i in range(num_nonterminal_states)] + [0.0]


def updateBelief(prevBelief, action, observation, difficulties, gamma):
    """Update question belief based on an 'observation' and 'gamma' (worker skill estimate).
    Uses Dai-AIJ13 paper belief update rules.

    Returns the new belief state.

    Arguments:
        prevBelief
        action - ignored
        observation - must be 0 or 1 (int/bool)
        difficulties - e.g. list [0.0, 0.1, ... 1.0]
        gamma - best estimate of skill for the worker providing observation
    """
    assert observation == 0 or observation == 1

    if prevBelief[-1] == 1.0:
        # in the terminal state, skip
        return prevBelief

    newBelief = []
    numDiffs = len(difficulties)

    for i in range(0, 2):  # true or false
        for j in range(0, numDiffs):
            diff = difficulties[j]
            state = i * numDiffs + j  # TERMINAL STATE IS THE LAST ELEMENT
            if observation == (1 - i):  # TRUE STATES ARE FIRST
                newBelief.append(calcAccuracy(gamma, diff) * prevBelief[state])
            else:
                newBelief.append(
                    (1 - calcAccuracy(gamma, diff)) * prevBelief[state])

    # NOTE terminal state is the LAST element
    newBelief = newBelief + [0.0]

    normalize(newBelief)
    return newBelief
