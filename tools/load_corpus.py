"""Load a corpus JSONL file into the SQLite database.

The app does this itself on first boot (backend/db.py bootstrap), so this is
only needed to load a different file, or to reload after wiping the DB.

Usage:
    python tools/load_corpus.py                      # ./corpus.jsonl, or the fixture if absent
    python tools/load_corpus.py path/to/file.jsonl
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend import db  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        path = Path(argv[1])
        is_fixture = path.resolve() == db.FIXTURE_CORPUS_PATH.resolve()
    else:
        path, is_fixture = db.resolve_corpus_path()
    if not path.exists():
        print(f"not found: {path}", file=sys.stderr)
        return 1
    db.init_db()
    rows = db.read_corpus(path)
    inserted = db.load_emails(rows)
    kind = "fixture" if is_fixture else "corpus"
    print(f"{kind}: {path}")
    print(f"read {len(rows)} rows, inserted {inserted} new, db {db.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
