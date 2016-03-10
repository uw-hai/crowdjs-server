from app import app
from flask.ext.security import login_required, current_user, auth_token_required
from schema.worker import Worker
from schema.answer import Answer
from schema.task import Task
from redis_util import redis_get_worker_assignments_var, redis_get_task_queue_var

def requester_token_match(requester_id):
    return str(current_user.id) == requester_id

def requester_token_match_and_task_match(requester_id, task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return (str(current_user.id) == requester_id and
            str(task.requester.id) == requester_id)

def requester_task_match(requester_id, task_id):
    try:
        task = Task.objects.get(id = task_id)
    except:
        return False
    return str(task.requester.id) == requester_id

    
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

def clear_task_from_redis(task_id):
    
    num_questions_deleted = 0
    for assign_strategy in ['min_answers']:
        task_queue_var = redis_get_task_queue_var(task_id,
                                                  assign_strategy)
        task_queue = app.redis.zrange(task_queue_var, 0, -1)
        num_questions_deleted += len(task_queue)
        app.redis.delete(task_queue_var)


    worker_assignments_deleted = 0
    for worker in Worker.objects():
        worker_assignments_var = redis_get_worker_assignments_var(
            task_id, worker.platform_id)
        worker_assignments_deleted += app.redis.delete(
            worker_assignments_var)
        

    return (num_questions_deleted, worker_assignments_deleted)
