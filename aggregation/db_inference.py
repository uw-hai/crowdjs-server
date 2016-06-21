# Inference routines that should run in the background
import schema
from util import majorityVote
import importlib
inf_mod = importlib.import_module("crowd-estimate.em")
from app import user_datastore
import datetime

def aggregate_task_majority_vote(task_id):
    """
    Assign majority vote labels to each question in the task.

    Returns:
        results - dict {q.id : majority_vote_label for each question q}
        with -1 if there were no votes on the question
    """
    questions = schema.question.Question.objects(task = task_id)

    labels = dict()

    for question in questions:
        answers = schema.answer.Answer.objects(question = question)
        q_id = str(question.id)
        ballot = [answer.value for answer in answers]
        if len(ballot) == 0:
            print "mv -1 (no votes) on question = ", q_id, question.name
            labels[q_id] = -1
        else:
            mv = majorityVote(ballot)[0]
            print "mv on question = ", q_id, question.name, ballot, mv
            labels[q_id] = mv

    print labels
    return labels

# TODO Should be part of a background process that periodicallly runs EM 
# on each task in the database
#NOTE Assumes all questions are binary
def aggregate_task_EM(task_id):
    """
    Within a given task, use the Expectation Maximization algorithm to
    estimate worker skills and question label probabilities + difficulties.
    Only uses the data contained in the task, i.e. does not use any
    worker history that might be elsewhere in our database.

    Returns:
        result - dict {
        'posteriors': dict {q.id : EM_posterior_estimate for each question q},
        'workers': dict {w.id : EM_skill_estimate for each worker w this task},
        'questions': dict {q.id : EM_difficulty_estimate for each question q}
        }
    """
    print "Agg Task EM called, getting answer objects", datetime.datetime.utcnow()

    #get all completed answers from the task
    answers = schema.answer.Answer.objects(task = task_id, status='Completed')

    #debug time taken by EM run
    print "Agg Task EM start em", datetime.datetime.utcnow()

    result = run_em(answers)

    # Write to DB
    write_success = write_em(result)

    if not write_success:
        return {'error': 'failure when writing inference results to DB'}

    #debug time taken by EM run
    print "Agg Task EM ret", datetime.datetime.utcnow()

    return result

def run_em(answers):
    """
    Loads Answer DB objects into inference module (EM) format,
    runs EM, returns the result.

    answers argument: sequence of Answer objects on which to run EM.
    """
    print "run_em called", datetime.datetime.utcnow()

    # reformat for EM
    em_votes = {}
    em_workers = {}
    em_questions = {}
    for answer in answers:
        w_id = str(answer.worker.id)
        q_id = str(answer.question.id)
        label = int(answer.value)
        em_votes[(w_id,q_id)] = {'vote':label}
        #NOTE overwriting with default value repeatedly
        #TODO allow using prev q.inference_results and/or gold data as initial estimates
        em_workers[w_id] = {'skill': None}
        em_questions[q_id] = {'difficulty': None} 
    
    print "run_em loaded data", datetime.datetime.utcnow()

    print "em_votes", em_votes
    print "em_workers", em_workers
    print "em_questions", em_questions
    start = datetime.datetime.utcnow()
    res = inf_mod.estimate(em_votes, em_workers, em_questions)
    end = datetime.datetime.utcnow()
    print "EM algorithm took time =", str(end-start)

    return res

def write_em(res):
    """Write inference results to DB.

    Returns True if all data successfully written, False otherwise
    """

    posteriors = res['posteriors']
    skills = res['workers']
    difficulties = res['questions']

    timestamp = str(datetime.datetime.utcnow())

    for (q_id,posterior_est) in posteriors.iteritems():
        # grab difficulty estimate for this question
        difficulty_est = difficulties[q_id]

        q = schema.question.Question.objects.get(id=q_id)
        # NOTE overwrites previous EM results!
        q.inference_results['EM'] = {'timestamp':timestamp, 'posterior':posterior_est, 'difficulty':difficulty_est}
        q.save()

    for (w_id,skill_est) in skills.iteritems():
        w = schema.worker.Worker.objects.get(id=w_id)
        # NOTE overwrites previous EM results!
        w.inference_results['EM'] = {'timestamp':timestamp, 'skill':skill_est}
        w.save()

    return True
