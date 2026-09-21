---
name: start
description: Start the Jev Inbox Lab backend (:8000) and frontend (:5173) in the background and report the health check.
---

Run the start script from the repo root and show its output:

```bash
./scripts/start.sh
```

Then tell the user the app is at http://localhost:5173. If the script says
`.env` was just created or the key is empty, tell them to add
`TYPESAFE_API_KEY` to `.env` before starting a run; do not read or print the
key. If it times out, read `.run/backend.log` and `.run/frontend.log` and
report the error.
