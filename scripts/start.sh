#!/usr/bin/env bash
# Start the Jev Inbox Lab backend (uvicorn :8000) and frontend (vite :5173)
# as background processes. Logs and pid files go in .run/ (gitignored).
# Safe to re-run: anything already listening is left alone.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .run

if [ ! -f .env ]; then
  cp .env.example .env
  echo "created .env from .env.example - add your key after TYPESAFE_API_KEY= and start again"
  exit 1
fi
if ! grep -qE '^TYPESAFE_API_KEY=.+' .env; then
  echo "TYPESAFE_API_KEY is empty in .env - runs will be refused until it is set"
fi

listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

if listening 8000; then
  echo "backend already listening on :8000"
else
  nohup uvicorn backend.app:app --port 8000 > .run/backend.log 2>&1 &
  echo $! > .run/backend.pid
  echo "backend starting (pid $!) -> .run/backend.log"
fi

if listening 5173; then
  echo "frontend already listening on :5173"
else
  root="$PWD"
  ( cd frontend && exec nohup npm run dev > "$root/.run/frontend.log" 2>&1 ) &
  echo $! > .run/frontend.pid
  echo "frontend starting (pid $!) -> .run/frontend.log"
fi

for i in $(seq 1 30); do
  if curl -s -m 1 localhost:8000/api/health >/dev/null && listening 5173; then
    echo
    curl -s localhost:8000/api/health; echo
    echo "open http://localhost:5173"
    exit 0
  fi
  sleep 0.5
done
echo "timed out waiting - check .run/backend.log and .run/frontend.log"
exit 1
