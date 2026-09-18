# Job application pipeline

Built on cv-router. cv-router answers "which of my CVs, and what should I
change?". The pipeline wraps that answer in the rest of the loop: find
postings, decide which are worth applying to, tailor the CV, stage the
application for you to send, and track what happens.

```
job boards ──► fetch ──► pre-screen ──► cv-router ──► route ──┬─► auto ───► tailor ──► staged ──► you submit
 (public API)            (free)         (2 calls)   by fit   ├─► review ─► you approve ──┘
                                                              └─► skip
                                  every branch ends in the tracker
```

cv-router keeps doing exactly what it did — the watcher, the portal, the index.
The pipeline calls it; it does not replace any of it.

## Quick start

```bash
cp pipeline.example.toml pipeline.toml      # boards, filters, thresholds
cp profile.example.toml profile.toml        # your details, for form pre-fill
./install.sh                                # installs the timer, does not start it

python run_pipeline.py --dry-run            # rehearse: fetch for real, route on a copy
python run_pipeline.py --max-matches 5      # a small real batch
python -m pipeline.review                   # approve or skip the review queue
python -m pipeline.submit --next            # stage the best application; you click submit
python -m pipeline.tracker export           # data/job_tracker.xlsx
```

Once a dry run and a small batch look right:

```bash
systemctl --user enable --now cv-router-pipeline.timer    # every ~45 min
```

## Components

| Spec component | Here | Notes |
|---|---|---|
| Job Sourcing Service | `pipeline/fetch.py`, `pipeline/sources.py` | Greenhouse, Lever, Ashby public JSON; `--manual` for anything else |
| cv-router headless entry | `matcher.py`, `match.py`, `POST /api/v1/match` | the logic the portal already used, lifted out and shared |
| Orchestrator | `pipeline/orchestrate.py` | pre-screen, dedupe, budget, thresholds; resumable |
| CV Auto-Tailoring Engine | `pipeline/tailor.py`, `templates/cv.html` | see below — the spec's template did not exist |
| Submission Assistant | `pipeline/submit.py` | Tier 1 staged, Tier 2 manual, never clicks |
| Tracker Service | `pipeline/tracker.py`, `pipeline/db.py` | SQLite is the store; the xlsx is exported from it |
| (calibration) | `pipeline/calibrate.py` | label 10-15 jobs, get thresholds that match you |

## Where this departs from the spec, and why

**A free pre-screen runs before any model call.** Each cv-router evaluation is
two calls. A hundred a day is two hundred calls, more than a Claude plan
absorbs. So every posting first goes through filters that cost nothing — title,
place, language, age, years of experience asked for, right to work — and a
score of how much of *your* skill vocabulary the ad uses, read from cv-router's
index. Only the best-screened reach the model, within `daily_match_budget`.

This was measured, not assumed: on the first real batch, five evaluations all
came back as skips, and four of the five were for reasons the pre-screen can
read in the ad text — "3+ years", "legal eligibility to work in France". Those
filters now catch them before they cost anything.

**The structured CV template did not exist.** Your CVs are PDFs from a CV
builder. So each base CV is extracted once into a structured document, text
copied verbatim, cached by content. The extraction is checked against the PDF —
under 85% of the words kept, it is refused. Edits are then applied only where
the text they quote is found; nothing is written freely.

**Tailored CVs go to `applications/`, not the downloads folder.** Routing them
through the watcher would fill the CV library with one-off per-job copies, and
spend a model call classifying each. Set `register_in_cv_library = true` to
have them indexed anyway.

**SQLite is the tracker; the xlsx is a view.** A spreadsheet cannot be written
safely by several processes, and cannot be queried for the weekly rollup.
`job_tracker.xlsx` is regenerated from the database after every run.

**Submission fills less than "every field".** Identity, contact, links and the
CV upload are filled. Work authorisation, salary, demographic and custom
questions are left for you: answering them on your behalf could misrepresent
you, and on the three live forms checked (Greenhouse, Lever, Ashby) they number
5 to 44 per form.

## Tailoring: what may change, what may not

| May change | Never changes |
|---|---|
| headline, profile paragraph | name, email, phone |
| experience and project bullets | employers, schools |
| skills lists (reword, add, reorder) | dates, places |

Every refused edit is kept with its reason in a `.json` beside the PDF.
Measured on your CV against a real ad: 5 of 6 edits applied; the sixth tried
to rewrite your degree dates and place, and was refused.

The rendered CV is a single column of real text with standard headings — what
an ATS parses best. It is read back with `pdftotext` before use: the name must
be there, every applied edit must be readable, and it must fit `max_pages`.
The layout tightens in steps to fit one page, stopping at a readable floor.
It does **not** look like your FlowCV design: no photo, no sidebar.

## Guard rails

| Rule | Enforced by |
|---|---|
| You click submit, always | `submit.py` contains no `click()`, no key press; a test fails if one appears |
| No CAPTCHA circumvention | nothing interacts with them; their presence is reported to you |
| LinkedIn / Indeed never automated | not sourced; `submit.py` treats any non-Greenhouse/Lever/Ashby host as manual |
| Never apply twice | company + normalised title checked against the tracker before evaluation |
| One role posted per region counts once | twins collapsed; the best-placed posting is kept |
| Spread load on job boards | per-board refetch interval, boards per run, delay between boards, jittered timer |
| Bounded model spend | daily budget, charged before each call; a job failing twice is parked |
| A scheduled run cannot submit | `submit` refuses to run without an interactive terminal |

## What the first real run showed

Eighteen company boards, 1,898 postings:

| | Postings | |
|---|---|---|
| title in your target roles | 371 | 20% |
| + a place you can work | 36 | 1.9% |
| + every filter | 7 | 0.4% |

The binding constraint is **place**, not quota: these companies mostly hire
on-site in the US and the EU, and most French ads require EU work
authorisation. At this rate the configured boards yield a handful of real
candidates a week, not a hundred a day.

Volume will come from where jobs that fit you are posted, not from evaluating
more of these. Candidates for new sources, each with its own terms to respect:
remote-job boards with public APIs (Remotive, RemoteOK, Arbeitnow, Himalayas),
and ATS platforms Moroccan employers use (SmartRecruiters and Workable both
publish public posting APIs). LinkedIn and Rekrute postings can go in by hand:

```bash
python -m pipeline.fetch --manual ad.txt --company Acme --title "ML Engineer" --url https://...
```

## Measuring success

The spec measures response rate per application sent, not applications sent.
Record outcomes as they come:

```bash
python -m pipeline.tracker set <job_id> interview --notes "call with the CTO"
python -m pipeline.tracker weekly
```

The Weekly sheet puts applied, reviewed and skipped side by side per fit-score
bucket, with response and interview rates. After a few weeks it tells you
whether the ≥70 bucket really answers more often than 40-69 — which is the only
real test of the thresholds. Until then, `python -m pipeline.calibrate label`
lets you judge jobs yourself and see which thresholds reproduce your judgement.

## Tests

```bash
./.venv/bin/python test_pipeline.py     # 60+ checks: parsing, filters, routing, budget,
                                        # tailoring guards, submission guard rails, tracker
```
