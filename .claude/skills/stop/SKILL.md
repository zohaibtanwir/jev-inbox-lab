---
name: stop
description: Stop the Jev Inbox Lab backend and frontend started by /start.
---

Run the stop script from the repo root and show its output:

```bash
./scripts/stop.sh
```

Report what was stopped. If it says something is still listening, show the
lsof line it printed and ask before killing anything else.
