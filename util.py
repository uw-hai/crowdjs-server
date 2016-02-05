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


def calcAccuracy(gamma, d):
    return (1.0 / 2) * (1.0 + (1.0 - d) ** gamma)


def normalize(array):
    sum = 0.0
    for i in range(0, len(array)):
        sum += array[i]
    for i in range(0, len(array)):
        array[i] = array[i] / sum
    return array


def updateBelief(prevBelief, action, observation, difficulties, gamma):
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
