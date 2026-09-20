"""Generate synthetic fixtures. Deterministic — re-running gives identical output.

Writes:
  fixtures/corpus.sample.jsonl   50 synthetic emails, same field shape as the
                                 real corpus: {id, from, subject, date, body}
  fixtures/runs.sample.json      two fake runs with fake Jev answers in the
                                 verified wire shape, for endpoint stubs
  fixtures/diff.sample.json      a precomputed diff of those two runs

Nothing here comes from a real mailbox. Every name, company and address is
made up; domains use the reserved .example TLD.

Usage:
    python tools/gen_fixture.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.questions import (  # noqa: E402
    CATEGORY_OPTIONS,
    DEADLINE_PRESSURE_LEVELS,
    IMPORTANCE_LEVELS,
    get_question_set,
)

FIXTURES_DIR = REPO_ROOT / "fixtures"
CORPUS_OUT = FIXTURES_DIR / "corpus.sample.jsonl"
RUNS_OUT = FIXTURES_DIR / "runs.sample.json"
DIFF_OUT = FIXTURES_DIR / "diff.sample.json"

COST_PER_INPUT_TOKEN = 0.042 / 1_000_000

# ---------------------------------------------------------------------------
# The 50 emails.
#
# `intent` is the label the generator uses to fabricate plausible answers. It
# is NOT ground truth and is NOT written to the corpus file. Fields:
#   cat        intended category
#   imp        importance level 0..3
#   reply      needs_reply probability target
#   spam       is_spam target
#   auto       is_automated target
#   money      money_involved target
#   dl         has_deadline target
#   press      deadline_pressure level 0..3 (only meaningful if dl high)
#   confuse    optional list of categories the model would plausibly confuse
#              this with; drives lower confidence and run-to-run flips
# ---------------------------------------------------------------------------

E = []  # list of (email dict, intent dict)


def add(id_, from_, subject, days_ago, hour, body, **intent):
    date = (datetime(2026, 9, 20, tzinfo=timezone.utc)
            - timedelta(days=days_ago) + timedelta(hours=hour))
    E.append((
        {
            "id": id_,
            "from": from_,
            "subject": subject,
            "date": date.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "body": body.strip(),
        },
        intent,
    ))


# ---- personal (5) ---------------------------------------------------------

add("smp001", "Amara Okafor <amara.okafor@example.com>", "Sunday lunch?", 2, 10, """
Hey,

Are you around this Sunday? Thinking of doing a late lunch at ours, nothing
fancy, just a roast and whoever is free. Kwame is bringing his new partner so
it would be nice to have a friendly face there.

Let me know either way by Friday-ish so I know how much to cook.

A x
""", cat="personal", imp=2, reply=0.95, spam=0.01, auto=0.02, money=0.03, dl=0.55, press=2)

add("smp002", "Rashid T <rashid.t@example.com>", "Photos from the lake", 6, 19, """
Finally got round to going through the photos from the lake weekend. Put the
good ones in the shared album, link below. The one of your mum falling asleep
in the deckchair is going on the fridge whether she likes it or not.

https://photos.example/album/lake-2026

Dad
""", cat="personal", imp=1, reply=0.35, spam=0.01, auto=0.03, money=0.01, dl=0.02, press=0)

add("smp003", "Priya Nair <priya.n@example.com>", "Can you send me the sourdough recipe", 4, 14, """
Hi!

I have been meaning to ask since the dinner party. Could you send me your
sourdough recipe? Specifically the hydration and how long you do the cold
proof. Mine keeps coming out flat and I suspect I am rushing the bulk.

No rush, whenever you get a sec.

Priya
""", cat="personal", imp=1, reply=0.92, spam=0.01, auto=0.02, money=0.01, dl=0.03, press=0)

add("smp004", "Tom Whitfield <tom.whitfield@example.com>", "Flat keys this weekend", 1, 9, """
Mate, I am away Fri to Mon and the plumber is coming Saturday morning between
8 and 10 to look at the boiler. Any chance you could let him in? Keys are with
you already I think from last time.

Need to confirm with him by Thursday evening or he will give the slot away.

Cheers
Tom
""", cat="personal", imp=3, reply=0.96, spam=0.01, auto=0.02, money=0.05, dl=0.92, press=3)

add("smp005", "Leila Haddad <leila@example.com>", "Thank you!", 9, 21, """
Just wanted to say thank you for coming on Saturday and for the book. I
started it on the train home and I am already halfway through. You were right
about the second chapter.

See you at the next one.

Leila
""", cat="personal", imp=1, reply=0.30, spam=0.01, auto=0.02, money=0.01, dl=0.02, press=0)

# ---- professional (5) -----------------------------------------------------

add("smp006", "Marcus Chen <marcus.chen@harbourlane.example>",
    "Re: Q4 architecture review - slides due Thursday", 1, 11, """
Following up on this morning. The steering group has moved the review to
Friday 25th, which means I need your section of the deck by end of day
Thursday 24th at the latest so I can merge and rehearse.

Two things to cover:
1. The event bus migration and what it does to the p95 numbers
2. Whether we keep the SQLite reporting path or move it to the warehouse

Ten slides max. Shout if that is not doable.

Marcus
""", cat="professional", imp=3, reply=0.85, spam=0.01, auto=0.03, money=0.05, dl=0.97, press=3)

add("smp007", "Sofia Almeida <sofia@brightfold.example>",
    "Contract renewal for the data platform work", 3, 15, """
Hi,

Our current statement of work ends on 31 October. We would like to extend for
another six months at the same day rate, with the scope widened to include the
ingestion rewrite we discussed.

Could you confirm you have capacity, and whether the rate holds? If so I will
get procurement to issue the paperwork. They need it signed before the 15th
for it to land in the Q4 budget.

Best,
Sofia
""", cat="professional", imp=3, reply=0.94, spam=0.01, auto=0.03, money=0.88, dl=0.85, press=1)

add("smp008", "Northgate Talent <recruiting@northgate.example>",
    "Interested in a Staff Engineer role?", 5, 13, """
Hi there,

I came across your profile and thought you might be a fit for a Staff
Engineer position with one of our clients, a Series B fintech in London.
Hybrid, three days in office, salary in the region of 140-160k plus equity.

If you are open to a conversation this week or next, reply with a couple of
times that suit and I will set up a call.

Kind regards,
Jen Lawson
Northgate Talent
""", cat="professional", imp=1, reply=0.55, spam=0.25, auto=0.45, money=0.40, dl=0.10, press=0,
    confuse=["marketing", "other"])

add("smp009", "Daniel Roth <d.roth@harbourlane.example>", "Notes from today's client call", 2, 17, """
Notes from the Brightfold call, for the record. No action for you.

- They are happy with the ingestion latency after the batching change
- Sofia wants a written summary of the retry policy before renewal
- Next check-in is the first week of October, Marcus to schedule

Daniel
""", cat="professional", imp=1, reply=0.08, spam=0.01, auto=0.03, money=0.05, dl=0.05, press=0)

add("smp010", "Hana Sato <hana.sato@kestrel.example>", "Speaking slot at the Bristol meetup", 4, 12, """
Hi,

We have a 25 minute slot open at the Bristol Data Engineering meetup on
Wednesday 8 October and your talk on evaluating small models came up as a
suggestion. Would you be up for it?

I need to lock the line-up by Monday 29th so the venue can print the
schedule. A title and two-line abstract is all I need for now.

Thanks,
Hana
""", cat="professional", imp=2, reply=0.93, spam=0.01, auto=0.03, money=0.03, dl=0.90, press=2)

# ---- finance (5) ----------------------------------------------------------

add("smp011", "Northwind Bank <statements@northwindbank.example>",
    "Your September statement is ready", 3, 6, """
Your statement for the period 20 August to 19 September is now available to
view in online banking.

Account ending 4471
Closing balance: 3,208.14 GBP

To view your statement, log in and go to Statements and documents. This is an
automated message. Please do not reply.
""", cat="finance", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.90, dl=0.03, press=0,
    confuse=["account_admin"])

add("smp012", "LedgerPay <noreply@ledgerpay.example>",
    "Payment received: 1,250.00 GBP from Brightfold Ltd", 7, 10, """
You have received a payment.

From: Brightfold Ltd
Amount: 1,250.00 GBP
Reference: INV-2026-031
Expected in your account: within 1 working day

View the transaction in your LedgerPay dashboard.
""", cat="finance", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.98, dl=0.02, press=0)

add("smp013", "CloudStack Billing <billing@cloudstack.example>",
    "Invoice #48213 due 30 September", 4, 8, """
Invoice #48213 for your CloudStack account is now available.

Amount due: 84.60 USD
Due date: 30 September 2026
Payment method on file: card ending 2210 (auto-pay enabled)

No action is needed if auto-pay is enabled. If your card has expired, update
it before the due date to avoid service interruption.
""", cat="finance", imp=2, reply=0.02, spam=0.02, auto=0.97, money=0.98, dl=0.80, press=1,
    confuse=["account_admin"])

add("smp014", "Revenue Office <noreply@revenueoffice.example>",
    "Self assessment: file and pay by 31 January", 12, 9, """
This is a reminder that your self assessment tax return for the 2025 to 2026
tax year must be filed online, and any tax owed paid, by 31 January 2027.

Filing early gives you more time to arrange payment. Late filing incurs an
automatic 100 GBP penalty.

You can file at any time through your online account.
""", cat="finance", imp=2, reply=0.02, spam=0.03, auto=0.97, money=0.92, dl=0.93, press=0)

add("smp015", "Meridian Insure <accounts@meridianinsure.example>",
    "Your home insurance renews on 12 October", 5, 7, """
Your home insurance policy MI-5520917 is due for renewal on 12 October 2026.

New annual premium: 412.80 GBP (last year: 378.50 GBP)

Your policy will renew automatically unless you tell us otherwise before the
renewal date. To review your cover or cancel auto-renewal, log in to your
account or call us on the number on your policy documents.
""", cat="finance", imp=2, reply=0.03, spam=0.02, auto=0.96, money=0.97, dl=0.88, press=1,
    confuse=["account_admin"])

# ---- shopping_order (5) ---------------------------------------------------

add("smp016", "Kelp & Co <orders@kelpandco.example>", "Order KC-77812 confirmed", 6, 20, """
Thanks for your order!

Order number: KC-77812
1 x Linen shirt, navy, M - 58.00 GBP
1 x Wool socks, 3 pack - 18.00 GBP
Delivery: standard, free
Total charged: 76.00 GBP

We will email you again when it ships. Estimated delivery 3 to 5 working days.
""", cat="shopping_order", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.85, dl=0.03, press=0)

add("smp017", "ParcelWave <shipping@parcelwave.example>", "Your parcel is out for delivery today", 0, 7, """
Good morning. Your parcel from Kelp & Co is out for delivery today and should
arrive between 11:40 and 14:40.

Tracking: PW7731920048
No signature required. If you are out we will leave it in your safe place
(porch) as per your preferences.
""", cat="shopping_order", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.10, dl=0.08, press=0)

add("smp018", "Lumen Audio Support <support@lumenaudio.example>",
    "Return approved - refund on its way", 8, 15, """
Hi,

We have received your returned Lumen One headphones and inspected them. The
return is approved and a refund of 149.00 GBP has been issued to your original
payment method. Please allow 5 to 7 working days for it to appear.

Sorry they were not right for you.

Lumen Audio Support
""", cat="shopping_order", imp=1, reply=0.05, spam=0.02, auto=0.70, money=0.95, dl=0.03, press=0,
    confuse=["finance"])

add("smp019", "GreenFork <orders@greenfork.example>",
    "Your grocery delivery slot: Tue 22 Sep 18:00-20:00", 1, 16, """
Your GreenFork delivery is booked.

Slot: Tuesday 22 September, 18:00 to 20:00
Items: 34
Estimated total: 61.20 GBP (final total confirmed at dispatch)

You can edit your order until 23:59 on Monday 21 September.
""", cat="shopping_order", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.70, dl=0.75, press=3)

add("smp020", "Bolt Bikes <help@boltbikes.example>",
    "We need your reply to process order BB-2291", 2, 11, """
Hi,

The frame size you ordered (54cm) is out of stock until November. We can
either ship the 56cm now, hold the order for the 54cm, or cancel and refund.

Please reply with your preference by Wednesday 23 September, otherwise we
will hold the order by default.

Thanks,
Ola
Bolt Bikes customer care
""", cat="shopping_order", imp=2, reply=0.95, spam=0.02, auto=0.25, money=0.60, dl=0.92, press=3)

# ---- travel (5) -----------------------------------------------------------

add("smp021", "Skylark <bookings@skylark.example>", "Booking confirmed: LHR to LIS, 3 Oct", 10, 22, """
Your booking is confirmed.

Booking reference: SK9Q2L
Outbound: Sat 3 Oct, LHR 10:35 to LIS 13:20, flight SK441
Return: Wed 7 Oct, LIS 14:05 to LHR 16:50, flight SK442
Passenger: 1 adult
Total paid: 186.40 GBP

Online check-in opens 24 hours before departure.
""", cat="travel", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.75, dl=0.15, press=0)

add("smp022", "RailNorth <noreply@railnorth.example>",
    "Your e-tickets for Manchester Piccadilly", 3, 18, """
Your e-tickets are attached and also available in the RailNorth app.

Outbound: Thu 24 Sep, London Euston 08:20 to Manchester Piccadilly 10:31
Coach C, seat 14, forward facing
Return: Thu 24 Sep, Manchester Piccadilly 18:15 to London Euston 20:28

Show the QR code at the barrier. No need to print.
""", cat="travel", imp=1, reply=0.02, spam=0.02, auto=0.98, money=0.20, dl=0.10, press=0)

add("smp023", "Casa Verde <reservations@casaverde.example>", "Check-in details for your stay", 4, 9, """
Ola!

Looking forward to hosting you from 3 to 7 October. Check-in is from 15:00.
The key box is to the left of the blue door; the code is in your booking
confirmation. If you arrive after 22:00 please message me on the number below
so I can make sure the street gate is unlocked.

The bakery two doors down opens at 7 and is very good.

Ines
""", cat="travel", imp=1, reply=0.30, spam=0.02, auto=0.35, money=0.05, dl=0.10, press=0)

add("smp024", "Skylark <alerts@skylark.example>",
    "Schedule change: your flight now departs 07:15", 2, 5, """
There has been a change to your booking SK9Q2L.

Flight SK441 on Sat 3 Oct will now depart LHR at 07:15 instead of 10:35,
arriving LIS at 10:00.

Please review the new time and accept the change within 7 days. If the new
time does not work you can change to another flight or request a full refund
at no charge.
""", cat="travel", imp=3, reply=0.05, spam=0.02, auto=0.97, money=0.30, dl=0.90, press=2)

add("smp025", "Drift Cars <hello@driftcars.example>", "Your rental pickup tomorrow at 09:00", 1, 12, """
A reminder that your Drift Cars rental starts tomorrow.

Pickup: Lisbon Airport, desk 4, 09:00
Vehicle class: compact
Return: 7 Oct, same location, by 12:00

Bring your driving licence and the card used for booking. A 250 EUR deposit
will be held on the card and released after return.
""", cat="travel", imp=2, reply=0.02, spam=0.02, auto=0.97, money=0.55, dl=0.60, press=3)

# ---- marketing (4) --------------------------------------------------------

add("smp026", "Kelp & Co <deals@kelpandco.example>", "48 hours only: 30% off everything", 3, 8, """
Our autumn sale is here.

30% off everything, no code needed, until midnight Sunday.

Knitwear, outerwear, the linen you loved this summer. Free delivery on orders
over 50 GBP.

Shop now: https://kelpandco.example/sale

You are receiving this because you shopped with us. Unsubscribe.
""", cat="marketing", imp=0, reply=0.01, spam=0.08, auto=0.98, money=0.45, dl=0.55, press=3)

add("smp027", "Lumen Audio <hello@lumenaudio.example>", "Meet the new Lumen Pro", 7, 14, """
Introducing Lumen Pro.

Forty hours of battery. Adaptive noise cancelling that actually adapts. A
case that does not scratch. Everything you told us about Lumen One, fixed.

Pre-order now for delivery in October: 229 GBP.

Unsubscribe | Manage preferences
""", cat="marketing", imp=0, reply=0.01, spam=0.06, auto=0.98, money=0.40, dl=0.05, press=0)

add("smp028", "Skylark <offers@skylark.example>", "Autumn fares from 29 GBP", 9, 7, """
Fancy a long weekend?

Autumn fares from 29 GBP one way to Porto, Lisbon, Malaga and Palermo. Travel
between 1 October and 15 December. Book by Sunday.

Book now: https://skylark.example/autumn

To stop receiving offers, update your preferences.
""", cat="marketing", imp=0, reply=0.01, spam=0.07, auto=0.98, money=0.40, dl=0.45, press=2,
    confuse=["travel"])

add("smp029", "Notably <team@notably.example>", "You are missing out on Notably Pro", 5, 16, """
Hi,

You have been using Notably free for six months. Nice. But you have hit the
sync limit twice this month, and every time you do, a note goes unsynced.

Notably Pro removes the limit, adds version history, and costs less than a
coffee a week. Try it free for 14 days.

Upgrade now.

The Notably team
""", cat="marketing", imp=0, reply=0.02, spam=0.06, auto=0.96, money=0.45, dl=0.05, press=0,
    confuse=["account_admin"])

# ---- newsletter (5) -------------------------------------------------------

add("smp030", "Bytes & Bits <weekly@bytesandbits.example>",
    "Bytes & Bits #214: the SQLite renaissance", 5, 6, """
Issue 214

This week: why so many teams are quietly moving small services back to
SQLite, what WAL mode actually buys you, and the one setting almost everyone
gets wrong.

Also: a good thread on structured outputs from small models, a benchmark that
is less wrong than most, and a tool for diffing JSON that I now use daily.

Read online: https://bytesandbits.example/214

You are subscribed as a weekly reader. Unsubscribe.
""", cat="newsletter", imp=1, reply=0.01, spam=0.03, auto=0.95, money=0.02, dl=0.02, press=0)

add("smp031", "The Long Read <digest@thelongread.example>", "Sunday edition: five essays", 6, 8, """
Sunday edition

1. On the disappearance of the corner shop
2. What a 19th century lighthouse keeper's diary teaches about attention
3. The case for boring infrastructure
4. A short history of the paperclip
5. Why translation is harder than it looks

Roughly forty minutes of reading. Enjoy your Sunday.
""", cat="newsletter", imp=1, reply=0.01, spam=0.03, auto=0.96, money=0.01, dl=0.02, press=0)

add("smp032", "Harbour Lane <newsletter@harbourlane.example>",
    "Harbour Lane monthly: what shipped in August", 14, 10, """
What shipped in August

- Event bus migration completed for three services
- New reporting dashboard in beta
- Two new engineers joined the platform team, welcome Priya and Sam

Coming in September: the SQLite reporting decision, and the Q4 planning
offsite.

Questions? Reply to this email and it goes to the comms team.
""", cat="newsletter", imp=1, reply=0.05, spam=0.02, auto=0.90, money=0.02, dl=0.03, press=0,
    confuse=["professional", "marketing"])

add("smp033", "Maria Bakes <notes@mariabakes.example>",
    "Why I stopped using commercial yeast", 8, 12, """
Hi everyone,

Long one this week. About two years ago I stopped buying commercial yeast
entirely and I want to explain why, what changed in my baking, and what I
would tell someone thinking about doing the same.

Short version: it is slower, it is better, and it is not for everyone.

Read the full post (about 12 minutes).

If you enjoy these, consider a paid subscription. It keeps the lights on.
""", cat="newsletter", imp=1, reply=0.02, spam=0.03, auto=0.92, money=0.15, dl=0.02, press=0,
    confuse=["marketing"])

add("smp034", "Kestrel <updates@kestrel.example>", "Kestrel product update: September", 4, 9, """
Hello from Kestrel

Here is what is new this month:

- Faster search across workspaces
- Shared filters, so your team sees the same view
- A new integration with Notably

We also raised prices for new customers. Existing plans are unchanged.

Read the full changelog. If you would like a walkthrough of the new features,
book a call with our team.
""", cat="newsletter", imp=1, reply=0.02, spam=0.03, auto=0.95, money=0.20, dl=0.03, press=0,
    confuse=["marketing"])

# ---- account_admin (5) ----------------------------------------------------

add("smp035", "Northwind Bank <security@northwindbank.example>",
    "New sign-in from an unrecognised device", 1, 23, """
We noticed a new sign-in to your online banking.

Device: iPhone
Location: Manchester, UK (approximate)
Time: 19 Sep 2026, 22:41

If this was you, no action is needed. If you do not recognise this sign-in,
lock your account immediately in the app or call the number on your card.
""", cat="account_admin", imp=2, reply=0.02, spam=0.04, auto=0.98, money=0.10, dl=0.10, press=0,
    confuse=["finance"])

add("smp036", "Notably <noreply@notably.example>", "Your password was changed", 3, 20, """
The password for your Notably account was changed on 17 Sep 2026 at 19:12.

If you made this change, you can ignore this email.

If you did not change your password, reset it now and review your active
sessions.
""", cat="account_admin", imp=2, reply=0.01, spam=0.03, auto=0.99, money=0.02, dl=0.05, press=0)

add("smp037", "CloudStack <no-reply@cloudstack.example>", "Verify your new email address", 2, 14, """
You recently added a new email address to your CloudStack account.

Click the link below to verify it. The link expires in 24 hours.

https://cloudstack.example/verify?token=REDACTED

If you did not request this change, ignore this email and the address will
not be added.
""", cat="account_admin", imp=2, reply=0.01, spam=0.04, auto=0.99, money=0.02, dl=0.85, press=3)

add("smp038", "ParcelWave <support@parcelwave.example>",
    "Terms of service update effective 1 October", 6, 11, """
We are updating our terms of service and privacy policy, effective 1 October
2026.

The main changes clarify how we use delivery photos and how long we keep
tracking data. You do not need to do anything; by continuing to use ParcelWave
after 1 October you accept the updated terms.

Read the updated terms.
""", cat="account_admin", imp=0, reply=0.01, spam=0.03, auto=0.99, money=0.02, dl=0.20, press=1)

add("smp039", "Northwind Bank Secure <support@northwind-bank-secure.example>",
    "Your account has been limited - verify now", 1, 4, """
Dear Customer,

We have detected irregular activity and your account access has been LIMITED.
To restore full access you must verify your identity within 12 hours.

Verify now: http://northwind-bank-secure.example/restore/login

Failure to verify will result in permanent suspension of your account.

Northwind Bank Security Team
""", cat="account_admin", imp=0, reply=0.02, spam=0.94, auto=0.97, money=0.35, dl=0.80, press=3,
    confuse=["other", "finance"])

# ---- learning_cert (4) ----------------------------------------------------

add("smp040", "CertHub <exams@certhub.example>",
    "Your Cloud Architect exam is scheduled for 14 Oct", 3, 13, """
Your exam is booked.

Exam: Certified Cloud Architect, Professional
Date: Wednesday 14 October 2026, 09:00
Format: online proctored
Duration: 120 minutes

You may reschedule free of charge up to 48 hours before the exam. Run the
system check on the computer you will use at least a day before.
""", cat="learning_cert", imp=2, reply=0.02, spam=0.02, auto=0.97, money=0.15, dl=0.70, press=1)

add("smp041", "LearnStack <courses@learnstack.example>",
    "Module 4 is now unlocked: Distributed consensus", 5, 7, """
Module 4 of Systems Design in Practice is now available.

Distributed consensus: Paxos, Raft, and when you do not need either.
Estimated time: 3 hours, plus one graded exercise.

You are 42% through the course. Keep going.
""", cat="learning_cert", imp=1, reply=0.01, spam=0.02, auto=0.98, money=0.02, dl=0.05, press=0,
    confuse=["newsletter"])

add("smp042", "CertHub <noreply@certhub.example>",
    "Congratulations - your certificate is ready to download", 20, 16, """
Congratulations!

You passed Certified Data Engineer, Associate with a score of 83%.

Your certificate and digital badge are ready to download from your CertHub
dashboard. The certification is valid for three years.
""", cat="learning_cert", imp=1, reply=0.01, spam=0.02, auto=0.98, money=0.02, dl=0.02, press=0)

add("smp043", "Ines Duarte <ines.duarte@example.com>", "Feedback on your capstone draft", 4, 18, """
Hi,

I read through the capstone draft. Overall it is in good shape; the
evaluation section is the strongest part. Two things I would change:

1. The related work section reads like a list. Say what each paper gets wrong.
2. The latency numbers need error bars or at least a note on variance.

Final submissions close on 10 October. If you send me a revised version by
the 5th I can give it one more pass.

Ines
""", cat="learning_cert", imp=2, reply=0.80, spam=0.01, auto=0.03, money=0.02, dl=0.90, press=1,
    confuse=["professional", "personal"])

# ---- social_notification (4) ----------------------------------------------

add("smp044", "Linkr <notifications@linkr.example>", "Marcus Chen commented on your post", 2, 12, """
Marcus Chen commented on your post "Evaluating small models without ground
truth":

"Really useful framing. Curious whether you saw the same confidence collapse
on the short inputs."

View comment | Reply
""", cat="social_notification", imp=1, reply=0.35, spam=0.02, auto=0.98, money=0.01, dl=0.02, press=0)

add("smp045", "Pixelgram <noreply@pixelgram.example>", "You have 3 new followers", 4, 21, """
3 people started following you this week.

lake.and.light
sourdough_sam
kwame.o

See who is following you.
""", cat="social_notification", imp=0, reply=0.01, spam=0.03, auto=0.99, money=0.01, dl=0.02, press=0)

add("smp046", "ForumHub <no-reply@forumhub.example>",
    "New reply in thread: SQLite WAL mode gotchas", 3, 9, """
There is a new reply in a thread you are following.

Thread: SQLite WAL mode gotchas
Reply by: dbnerd42

"Worth adding: the checkpoint starvation issue only bites if you have a long
running reader. For a web app with short transactions it basically never
happens."

View thread | Unfollow thread
""", cat="social_notification", imp=1, reply=0.05, spam=0.02, auto=0.98, money=0.01, dl=0.02, press=0)

add("smp047", "Evently <invites@eventlyapp.example>",
    "Priya Nair invited you to: Board games night", 5, 17, """
Priya Nair invited you to an event.

Board games night
Saturday 27 September, 19:00
Priya's place

Going? Yes / Maybe / No

Priya says: "Bring snacks. I have the games."
""", cat="social_notification", imp=1, reply=0.45, spam=0.02, auto=0.95, money=0.02, dl=0.40, press=2,
    confuse=["personal"])

# ---- other (2) ------------------------------------------------------------

add("smp048", "City Parking <noreply@cityparking.example>",
    "Penalty charge notice PCN-88210 - pay within 14 days", 2, 8, """
A penalty charge notice has been issued to vehicle registration AB26 XYZ.

Contravention: parked in a restricted street during prescribed hours
Location: Mill Lane
Date: 17 September 2026, 14:22
Amount: 70.00 GBP, reduced to 35.00 GBP if paid within 14 days of the date of
notice

Pay or challenge online at https://cityparking.example/pcn
""", cat="other", imp=3, reply=0.02, spam=0.06, auto=0.98, money=0.97, dl=0.95, press=2,
    confuse=["finance"])

add("smp049", "Mr. Adewale Bankole <win.notice@lottery-claims.example>",
    "URGENT: unclaimed funds in your name", 1, 3, """
Dear Beneficiary,

I am contacting you regarding unclaimed funds of 4,850,000.00 USD held in
your name at our institution. Due to regulatory deadlines this amount will be
forfeited unless claimed within 7 days.

To begin the release process kindly reply with your full name, address,
telephone number and a copy of your identification.

Yours faithfully,
Mr. Adewale Bankole
Senior Claims Officer
""", cat="other", imp=0, reply=0.03, spam=0.98, auto=0.60, money=0.70, dl=0.55, press=2)

add("smp050", "Kwame Osei <kwame.osei@example.com>", "That podcast episode", 3, 22, """
The episode I mentioned at Amara's is called "Slow Software" and it is the
one from March. The bit about SQLite is about forty minutes in. Thought of you
immediately.

No need to reply, just listen to it.

K
""", cat="personal", imp=1, reply=0.15, spam=0.01, auto=0.02, money=0.01, dl=0.02, press=0)

assert len(E) == 50, len(E)
assert len({e["id"] for e, _ in E}) == 50
assert {i["cat"] for _, i in E} == set(CATEGORY_OPTIONS), "missing a category"
for e, _ in E:
    assert len(e["body"]) <= 1500, (e["id"], len(e["body"]))


# ---------------------------------------------------------------------------
# Fake Jev answers in the verified wire shape.
# ---------------------------------------------------------------------------

def _round(x: float, nd: int = 2) -> float:
    return round(x + 0.0, nd)


def _norm(d: dict[str, float]) -> dict[str, float]:
    s = sum(d.values())
    out = {k: _round(v / s) for k, v in d.items()}
    # Fix rounding drift so the top entry absorbs it and the sum is 1.0.
    drift = _round(1.0 - sum(out.values()))
    top = max(out, key=out.get)
    out[top] = _round(out[top] + drift)
    return out


def fake_choice(rng: random.Random, options: list[str], intended: str,
                confuse: list[str] | None, flip: bool) -> dict:
    confuse = confuse or []
    top = intended
    if flip and confuse:
        top = confuse[0]
    if confuse:
        p_top = rng.uniform(0.45, 0.72)
    else:
        p_top = rng.uniform(0.91, 0.99)
    probs = {o: 0.0 for o in options}
    probs[top] = p_top
    rest = 1.0 - p_top
    others = [o for o in options if o != top]
    weights = []
    for o in others:
        if o in confuse or o == intended:
            weights.append(rng.uniform(3.0, 6.0))
        else:
            weights.append(rng.uniform(0.0, 0.25))
    wsum = sum(weights) or 1.0
    for o, w in zip(others, weights):
        probs[o] = rest * w / wsum
    probs = _norm(probs)
    ranked = sorted(probs.values(), reverse=True)
    conf = _round(max(0.0, min(1.0, ranked[0] - ranked[1] * 0.6)))
    return {
        "type": "choice",
        "choice": max(probs, key=probs.get),
        "confidence": conf,
        "probabilities": probs,
    }


def fake_score(rng: random.Random, levels: list[str], level: int) -> dict:
    n = len(levels)
    jitter = rng.uniform(-0.35, 0.35)
    centre = min(n - 1, max(0, level + jitter))
    raw = {}
    for i in range(n):
        raw[str(i)] = math.exp(-((i - centre) ** 2) / 0.18)
    probs = _norm(raw)
    score = sum(int(k) * v for k, v in probs.items())
    ranked = sorted(probs.values(), reverse=True)
    conf = _round(max(0.0, min(1.0, ranked[0] - ranked[1] * 0.5)))
    return {
        "type": "score",
        "score": _round(score),
        "confidence": conf,
        "legend": {str(i): lvl for i, lvl in enumerate(levels)},
        "probabilities": probs,
    }


def fake_noul(rng: random.Random, target: float) -> dict:
    v = target + rng.uniform(-0.06, 0.06)
    return {"type": "noul", "noul": _round(min(0.99, max(0.01, v)))}


def fake_answers(rng: random.Random, intent: dict, flip: bool) -> dict:
    options = list(CATEGORY_OPTIONS)
    return {
        "category": fake_choice(rng, options, intent["cat"], intent.get("confuse"), flip),
        "importance": fake_score(rng, IMPORTANCE_LEVELS, intent["imp"]),
        "needs_reply": fake_noul(rng, intent["reply"]),
        "is_spam": fake_noul(rng, intent["spam"]),
        "is_automated": fake_noul(rng, intent["auto"]),
        "money_involved": fake_noul(rng, intent["money"]),
        "has_deadline": fake_noul(rng, intent["dl"]),
        "deadline_pressure": fake_score(rng, DEADLINE_PRESSURE_LEVELS, intent["press"]),
    }


def fake_run(run_id: int, seed: int, started_at: datetime, worker_count: int,
             questions: dict, model_version: str, flip_rate: float) -> tuple[dict, list[dict]]:
    rng = random.Random(seed)
    answers_rows = []
    latencies = []
    t_in = t_out = 0
    failed = 0
    for idx, (email, intent) in enumerate(E):
        # One deliberate failure per run so the UI has an error row to show.
        if idx == 41 and run_id == 1:
            answers_rows.append({
                "email_id": email["id"], "answers": None, "latency_ms": 30012,
                "input_tokens": None, "output_tokens": None,
                "error": "HTTP 429 after 3 retries",
            })
            failed += 1
            continue
        flip = bool(intent.get("confuse")) and rng.random() < flip_rate
        ans = fake_answers(rng, intent, flip)
        in_tok = 380 + len(email["body"]) // 4 + rng.randint(-15, 15)
        out_tok = 64 + rng.randint(0, 24)
        lat = int(rng.lognormvariate(math.log(650), 0.35))
        latencies.append(lat)
        t_in += in_tok
        t_out += out_tok
        answers_rows.append({
            "email_id": email["id"], "answers": ans, "latency_ms": lat,
            "input_tokens": in_tok, "output_tokens": out_tok, "error": None,
        })
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    wall_ms = int(sum(latencies) / worker_count * 1.15)
    run = {
        "id": run_id,
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "finished_at": (started_at + timedelta(milliseconds=wall_ms)).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "worker_count": worker_count,
        "email_count": len(E),
        "model_version": model_version,
        "question_set_json": json.dumps(questions, separators=(",", ":")),
        "total_input_tokens": t_in,
        "total_output_tokens": t_out,
        "total_cost_usd": round(t_in * COST_PER_INPUT_TOKEN, 6),
        "avg_ms": round(sum(latencies) / len(latencies), 1),
        "p95_ms": float(p95),
        "per_second": round(len(latencies) / (wall_ms / 1000), 2),
        "failed_count": failed,
    }
    return run, answers_rows


# ---------------------------------------------------------------------------
# Diff of two runs (PRD section 8). Same rules the real endpoint will use.
# ---------------------------------------------------------------------------

DELTA_THRESHOLD = 0.10


def diff_runs(run_a: dict, rows_a: list[dict], run_b: dict, rows_b: list[dict]) -> dict:
    by_a = {r["email_id"]: r["answers"] for r in rows_a if r["answers"]}
    by_b = {r["email_id"]: r["answers"] for r in rows_b if r["answers"]}
    flips, conf_deltas, noul_deltas = [], [], []
    for eid in sorted(set(by_a) & set(by_b)):
        a, b = by_a[eid], by_b[eid]
        for qid in sorted(set(a) & set(b)):
            qa, qb = a[qid], b[qid]
            if qa["type"] == "choice" and qa["choice"] != qb["choice"]:
                flips.append({"email_id": eid, "question_id": qid,
                              "a": qa["choice"], "b": qb["choice"]})
            if "confidence" in qa and "confidence" in qb:
                d = round(qb["confidence"] - qa["confidence"], 2)
                if abs(d) > DELTA_THRESHOLD:
                    conf_deltas.append({"email_id": eid, "question_id": qid,
                                        "a": qa["confidence"], "b": qb["confidence"], "delta": d})
            if qa["type"] == "noul":
                d = round(qb["noul"] - qa["noul"], 2)
                if abs(d) > DELTA_THRESHOLD:
                    noul_deltas.append({"email_id": eid, "question_id": qid,
                                        "a": qa["noul"], "b": qb["noul"], "delta": d})
    qs_a = json.loads(run_a["question_set_json"])
    qs_b = json.loads(run_b["question_set_json"])
    question_changes = []
    for qid in sorted(set(qs_a) | set(qs_b)):
        for field in ("type", "instructions", "criteria"):
            va, vb = qs_a.get(qid, {}).get(field), qs_b.get(qid, {}).get(field)
            if va != vb:
                question_changes.append({"question_id": qid, "field": field, "a": va, "b": vb})
    summary = {k: run_a[k] for k in ("id", "started_at", "model_version", "worker_count", "email_count")}
    summary_b = {k: run_b[k] for k in ("id", "started_at", "model_version", "worker_count", "email_count")}
    return {
        "a": summary,
        "b": summary_b,
        "delta_threshold": DELTA_THRESHOLD,
        "category_flips": flips,
        "confidence_deltas": conf_deltas,
        "noul_deltas": noul_deltas,
        "question_changes": question_changes,
    }


def main() -> None:
    FIXTURES_DIR.mkdir(exist_ok=True)

    with CORPUS_OUT.open("w", encoding="utf-8") as fh:
        for email, _ in E:
            fh.write(json.dumps(email, ensure_ascii=False) + "\n")

    qs1 = get_question_set()
    # Run 2 is experiment 1 from the PRD: a vaguer learning_cert description.
    qs2 = get_question_set()
    qs2["category"]["criteria"]["learning_cert"] = "Learning."

    run1, rows1 = fake_run(1, seed=1, started_at=datetime(2026, 9, 20, 14, 2, 11, tzinfo=timezone.utc),
                           worker_count=16, questions=qs1, model_version="jev-1.13.0", flip_rate=0.0)
    run2, rows2 = fake_run(2, seed=2, started_at=datetime(2026, 9, 20, 14, 9, 47, tzinfo=timezone.utc),
                           worker_count=32, questions=qs2, model_version="jev-1.13.0", flip_rate=0.5)

    RUNS_OUT.write_text(json.dumps({
        "_note": "Synthetic. Fake answers in the verified Jev wire shape. Not model output.",
        "runs": [run1, run2],
        "answers": {"1": rows1, "2": rows2},
    }, indent=2) + "\n")

    DIFF_OUT.write_text(json.dumps(diff_runs(run1, rows1, run2, rows2), indent=2) + "\n")

    print(f"wrote {CORPUS_OUT.relative_to(REPO_ROOT)} ({len(E)} emails)")
    print(f"wrote {RUNS_OUT.relative_to(REPO_ROOT)} (2 runs)")
    print(f"wrote {DIFF_OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
