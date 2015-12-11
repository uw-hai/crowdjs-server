from flask.ext.security import login_required, current_user, auth_token_required
from schema.worker import Worker

def requester_token_match(requester_id):
    return str(current_user.id) == requester_id

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
