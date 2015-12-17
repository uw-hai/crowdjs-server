from flask.ext.security import login_required, current_user, auth_token_required
from schema.worker import Worker
from schema.answer import Answer
from schema.task import Task

def requester_token_match(requester_id):
    return str(current_user.id) == requester_id

def requester_token_match_and_task_match(requester_id, task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return (str(current_user.id) == requester_id and
            str(task.requester.id) == requester_id)
    
def get_or_insert_worker(worker_id, worker_source):
    if worker_source == 'mturk':
        try:
            worker = Worker.objects.get(platform_id = worker_id,
                                        platform_name = 'mturk')
        except:
            worker = Worker(platform_id = worker_id,
                            platform_name = 'mturk')
            worker.save()
        return worker
    else:
        return None

def get_alive_answers(question):
    answers = Answer.objects(question=question)
    answers = filter(lambda answer: answer.is_alive, answers)

    return answers
