#!/bin/bash

trap 'jobs -p | xargs kill' SIGINT EXIT KILL STOP QUIT

source venv/bin/activate
pip install -r requirements.txt

./run-redis.sh &

sleep 2.5

celery -A app.celery worker --loglevel=info &

sleep 3

flask run &

sleep 2

echo "Spawned PID: $(jobs -p | xargs)"

wait