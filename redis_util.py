# Synthesize variable names used in Redis
# No checking at the moment

def redis_get_worker_assignments_var(task_id, worker_id):
    return "assigned_task%s_worker%s" % (task_id, worker_id)

def redis_get_task_queue_var(task_id, strategy):
    return "queue_task%s_strategy%s" % (task_id, strategy)
