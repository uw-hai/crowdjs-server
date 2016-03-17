# Inference routines that should run in the background
import schema
from util import majorityVote

def aggregate_task_majority_vote(task_id):
    """
    Assign majority vote labels to each question in the task.

    Returns:
        results - dictionary {q_id:majority_vote_label for each question q_id}
    """
    questions = schema.question.Question.objects(task = task_id)

    labels = dict()

    for question in questions:
        answers = schema.answer.Answer.objects(question = question)
        q_id = str(question.id)
        ballot = [answer.value for answer in answers]
        mv = majorityVote(ballot)[0]
        print "mv on question = ", q_id, ballot, mv
        labels[q_id] = mv

    print labels
    return labels
