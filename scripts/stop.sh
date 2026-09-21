#!/usr/bin/env bash
# Stop the backend and frontend started by scripts/start.sh.
# Uses the pid files first, then anything still listening on the two ports.
set -uo pipefail
cd "$(dirname "$0")/.."

for name in backend frontend; do
  f=".run/$name.pid"
  if [ -f "$f" ]; then
    pid=$(cat "$f")
    if kill "$pid" 2>/dev/null; then echo "stopped $name (pid $pid)"; fi
    rm -f "$f"
  fi
done

for port in 8000 5173; do
  for pid in $(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null); do
    kill "$pid" 2>/dev/null && echo "stopped pid $pid on :$port"
  done
done

sleep 0.5
if lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "something is still listening:"; lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN
  exit 1
fi
echo "all stopped"
