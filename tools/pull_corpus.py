"""Normalise raw Gmail messages into corpus.jsonl.

The pull itself happens once, by hand, through the Gmail MCP — this script
does not talk to Gmail. It takes a JSON array of raw messages and writes the
frozen corpus with the field shape in PRD section 4:

    {"id": ..., "from": ..., "subject": ..., "date": ..., "body": ...}

Body handling: plain text only, quoted reply chains stripped, truncated to
BODY_MAX_CHARS. The truncation length is a deliberate design choice (PRD
experiment 2) — change BODY_MAX_CHARS and re-run to build a variant corpus.

Input shape expected (one object per message):

    {"id": "...", "from": "...", "subject": "...", "date": "...",
     "body": "...plain text..."}

Output goes to ./corpus.jsonl by default, which is gitignored. Never commit it.

Usage:
    python tools/pull_corpus.py raw_messages.json
    python tools/pull_corpus.py raw_messages.json --out corpus.jsonl --max-chars 1500
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BODY_MAX_CHARS = 1500

# Lines that begin a quoted reply chain. Everything from the first match on
# is dropped.
_QUOTE_STARTS = (
    re.compile(r"^On .+ wrote:\s*$", re.M),
    re.compile(r"^-{2,}\s*Original Message\s*-{2,}\s*$", re.M | re.I),
    re.compile(r"^From: .+\nSent: .+\nTo: .+", re.M),
    re.compile(r"^_{5,}\s*$", re.M),
)
_QUOTED_LINE = re.compile(r"^>.*$", re.M)
_BLANKS = re.compile(r"\n{3,}")

# Marketing mail as delivered by the Gmail MCP in PLAIN_TEXT mode: tracking
# URLs, markdown link debris, and preheader filler made of invisible chars.
_ANGLE_URL = re.compile(r"<\s*(?:https?://|mailto:|tel:)[^>]*>")
_MD_LINK = re.compile(r"\[([^\]]*)\]\((?:https?://|mailto:|tel:|#|//)[^)]*\)")
_BARE_URL = re.compile(r"(?:https?://|www\.)\S+")
_INVISIBLE = re.compile("[\u034f\u00ad\u200b\u200c\u200d\u2060\ufeff\u180e]")
_TABLE_PIPE_LINE = re.compile(r"^\s*(?:\|\s*)+$", re.M)
_TABLE_EDGE = re.compile(r"^\s*\|\s?|\s?\|\s*$", re.M)
_HSPACE = re.compile(r"[ \t\u00a0]{2,}")
_TRAILING = re.compile(r"[ \t]+$", re.M)


def strip_quotes(body: str) -> str:
    cut = len(body)
    for pat in _QUOTE_STARTS:
        m = pat.search(body)
        if m and m.start() < cut:
            cut = m.start()
    body = body[:cut]
    body = _QUOTED_LINE.sub("", body)
    return body


def strip_noise(body: str) -> str:
    body = _INVISIBLE.sub("", body)
    body = _ANGLE_URL.sub("", body)
    body = _MD_LINK.sub(r"\1", body)
    body = _BARE_URL.sub("", body)
    body = _TABLE_PIPE_LINE.sub("", body)
    body = _TABLE_EDGE.sub("", body)
    body = _HSPACE.sub(" ", body)
    body = _TRAILING.sub("", body)
    return body


def normalise_body(body: str, max_chars: int = BODY_MAX_CHARS) -> str:
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = strip_quotes(body)
    body = strip_noise(body)
    body = _BLANKS.sub("\n\n", body).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip()
    return body


def normalise(raw: dict, max_chars: int) -> dict:
    return {
        "id": str(raw["id"]),
        "from": raw.get("from", "").strip(),
        "subject": raw.get("subject", "").strip(),
        "date": raw.get("date", "").strip(),
        "body": normalise_body(raw.get("body", ""), max_chars),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw", type=Path, help="JSON array of raw messages")
    ap.add_argument("--out", type=Path, default=Path("corpus.jsonl"))
    ap.add_argument("--max-chars", type=int, default=BODY_MAX_CHARS)
    args = ap.parse_args(argv[1:])

    if args.out.name.startswith("fixtures"):
        print("refusing to write real mail under fixtures/", file=sys.stderr)
        return 2

    raw_rows = json.loads(args.raw.read_text(encoding="utf-8"))
    rows = [normalise(r, args.max_chars) for r in raw_rows]
    with args.out.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} messages to {args.out} (bodies <= {args.max_chars} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
