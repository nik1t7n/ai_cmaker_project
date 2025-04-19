#/bin/sh

uv run -m arq arq_jobs.WorkerSettings > arq.log 2>&1 &
PID1=$!

uv run -m bot.main > bot.log 2>&1 &
PID2=$!

tail -f arq.log bot.log &

wait $PID1
wait $PID2
