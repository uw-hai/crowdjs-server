web: gunicorn app:app --log-file=- --timeout=300 --max-requests 500
worker: celery -A app.celery worker --concurrency 3
beat: celery -A app.celery beat
