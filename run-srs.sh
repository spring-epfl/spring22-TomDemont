#!/bin/bash

trap 'jobs -p | xargs kill' SIGINT EXIT KILL STOP QUIT

./run-redis.sh &

sleep 1

celery -A app.celery worker --loglevel=info &

sleep 1

flask run &

echo "Spawned PID: $(jobs -p | xargs)"

wait