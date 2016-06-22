web: gunicorn app:app --log-file=- --timeout=300
worker: celery worker --app=app.app
