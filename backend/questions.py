"""Question set v1 (PRD section 6).

Eight questions, all sent in one Jev call per email. The dict below is the
exact `questions` object that goes on the wire, so it is also what gets
persisted verbatim into `runs.question_set_json`.

Wire shape (verified against https://docs.typesafe.ai/api.md, 20 Sep 2026):

    choice  criteria: { "<option>": "<description>", ... }
    noul    criteria: { "true": "<description>", "false": "<description>" }
    score   criteria: [ "<level 0>", "<level 1>", ... ]   # ordered, low -> high

Question ids are for our code only. They are not sent to the model, so every
question carries its full meaning in `instructions` and `criteria`.

The state object each question reads is:

    { "from": "...", "subject": "...", "date": "...", "body": "..." }

Questions may target a field by backticked path, e.g. `subject`.
"""

from __future__ import annotations

import copy
from typing import Any

QUESTION_SET_VERSION = "v1"

# Category options. Order matters only for display; the model sees the dict.
CATEGORY_OPTIONS: dict[str, str] = {
    "personal": (
        "A message typed by a friend, family member or acquaintance about "
        "non-work life: plans, favours, news, photos, thanks."
    ),
    "professional": (
        "Work-related mail from a colleague, client, recruiter or business "
        "contact, typed by a person: projects, meetings, contracts, roles."
    ),
    "finance": (
        "Concerns the recipient's money directly: bank statements, payments "
        "received or due, invoices, tax, insurance, fines."
    ),
    "shopping_order": (
        "About a specific purchase of goods: order confirmation, shipping, "
        "delivery slot, return, refund, or a question about an order."
    ),
    "travel": (
        "About a specific trip: flight, train or car booking, accommodation "
        "check-in, schedule change, pickup reminder."
    ),
    "marketing": (
        "Promotional mail whose purpose is to sell: sales, discounts, product "
        "launches, upsells, win-back offers. The recipient did not ask for "
        "this specific message."
    ),
    "newsletter": (
        "Periodic editorial content the recipient subscribed to read: issues, "
        "digests, essays, weekly round-ups. Informative rather than selling."
    ),
    "account_admin": (
        "Automated housekeeping about an account the recipient holds: sign-in "
        "alerts, password changes, email verification, terms updates, "
        "subscription renewals."
    ),
    "learning_cert": (
        "Courses, exams, certifications and study: exam scheduling, module "
        "unlocks, certificates issued, mentor feedback on coursework."
    ),
    "social_notification": (
        "An automated notification from a social platform or community: "
        "comments, followers, thread replies, event invites."
    ),
    "other": (
        "Does not fit any other option, or is unsolicited junk with no "
        "legitimate relationship to the recipient."
    ),
}

IMPORTANCE_LEVELS: list[str] = [
    "Ignorable: nothing to read or do; safe to never open.",
    "Worth a glance: mildly informative, no action required.",
    "Needs action this week: something to do, but not today.",
    "Act today: time-sensitive or blocking something else today.",
]

DEADLINE_PRESSURE_LEVELS: list[str] = [
    "More than a month away, or a soft target with no consequence.",
    "Within the next month.",
    "Within the next week.",
    "Within 48 hours, or already passed.",
]

QUESTIONS_V1: dict[str, dict[str, Any]] = {
    "category": {
        "type": "choice",
        "instructions": (
            "Which single category best describes this email, judged from "
            "`from`, `subject` and `body` together? Pick the option whose "
            "description fits the sender's purpose in writing."
        ),
        "criteria": CATEGORY_OPTIONS,
    },
    "importance": {
        "type": "score",
        "instructions": (
            "How important is this email for the recipient to read and act on, "
            "from ignorable to act today? Judge by what would be lost if it "
            "were never opened."
        ),
        "criteria": IMPORTANCE_LEVELS,
    },
    "needs_reply": {
        "type": "noul",
        "instructions": (
            "Does this email need a written reply from the recipient? A reply "
            "is needed when a person asked a question, requested something, or "
            "is waiting to hear back. Automated senders do not need replies."
        ),
        "criteria": {
            "true": "A person is waiting for the recipient to write back.",
            "false": "No reply expected, or the sender is a system.",
        },
    },
    "is_spam": {
        "type": "noul",
        "instructions": (
            "Is this email unsolicited or deceptive: junk, a scam, phishing, "
            "or a sender with no legitimate relationship to the recipient? "
            "Ordinary promotional mail from a company the recipient has dealt "
            "with is not spam."
        ),
        "criteria": {
            "true": "Unsolicited junk, scam or phishing.",
            "false": "A legitimate sender, even if promotional.",
        },
    },
    "is_automated": {
        "type": "noul",
        "instructions": (
            "Was this email generated and sent by a system rather than typed "
            "by a person? Order confirmations, alerts, notifications and mass "
            "mailings are automated. A message written to this recipient by a "
            "named individual is not."
        ),
        "criteria": {
            "true": "Sent by a system, template or bulk mailer.",
            "false": "Typed by a person for this recipient.",
        },
    },
    "money_involved": {
        "type": "noul",
        "instructions": (
            "Does this email concern a payment, charge, invoice, refund, fee, "
            "price or specific amount of money that affects the recipient?"
        ),
        "criteria": {
            "true": "A payment, charge, amount or price is central to the email.",
            "false": "No money is at stake for the recipient.",
        },
    },
    "has_deadline": {
        "type": "noul",
        "instructions": (
            "Does this email name a specific date or time by which the "
            "recipient must act? A stated event date alone is not a deadline "
            "unless the recipient has to do something before it."
        ),
        "criteria": {
            "true": "A date or time by which the recipient must act is stated.",
            "false": "No date by which the recipient must act.",
        },
    },
    # Speculative: only consumed when has_deadline > 0.5. The premise is
    # stated explicitly because the model cannot see the other answer.
    "deadline_pressure": {
        "type": "score",
        "instructions": (
            "Assume this email names a deadline by which the recipient must "
            "act. Relative to the email's `date`, how soon is that deadline? "
            "If no deadline is named, answer as if it were more than a month "
            "away."
        ),
        "criteria": DEADLINE_PRESSURE_LEVELS,
    },
}

# Questions whose answers are only meaningful given another answer.
SPECULATIVE: dict[str, dict[str, Any]] = {
    "deadline_pressure": {"gated_by": "has_deadline", "threshold": 0.5},
}


def get_question_set() -> dict[str, dict[str, Any]]:
    """Return a deep copy so callers cannot mutate the module-level set."""
    return copy.deepcopy(QUESTIONS_V1)
