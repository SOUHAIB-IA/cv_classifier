# cv-router

If you tailor your CV per application, you end up with eighty near-identical
PDFs called `resume-3 (2).pdf` and no idea which one to send.

cv-router started there and grew into the whole arc: it files the CVs you
already have, finds postings worth answering, picks the right CV for each one,
rewrites it for that ad, and hands you a finished application to send.

```
~/Downloads/resume-3 (2).pdf
        │
        ▼   read, classified, renamed, filed
~/Documents/CVs/2-Graduate/AI-ML-Engineering/
        Ada-LOVELACE_AI-ML-Engineer_RAG-MLOps_EN.pdf

  job boards ──► free pre-screen ──► cv-router scores it ──► CV tailored
                                                                  │
                                              you read and edit it ▼
                                                        you send it ──► tracked
```

An LLM reads the whole document — profile, skills, projects — so nothing turns
on a filename or a stale job title at the top of the page.

## Four pages

Everything is one local web app on <http://127.0.0.1:8770>. `Ctrl+K` searches
every posting from any of them.

| | |
|---|---|
| **Analyser** | paste an ad, get the CV to send and what to change first |
| **Pipeline** | the journey of a posting, what is waiting for you, and the graphs |
| **Données** | every posting ever seen: search, filter, sort, export as CSV |
| **Réglages** | every setting, with the sentence that explains it |

## Job application pipeline

cv-router is also the engine of a fuller pipeline: it sources postings from
public job boards, pre-screens them for free, has cv-router pick and score the
CV, tailors it, stages the application for you to submit, and tracks the
outcome. See **[PIPELINE.md](PIPELINE.md)**.

The dashboard at `/pipeline` shows the whole journey, labels every stage with
who moves it along, and graphs what the pipeline is actually doing: collection
and evaluation over 30 days, applications per day, the distribution of fit
scores against your thresholds, and the response rate per fit bucket, which is
what tells you whether the thresholds are set right.

### Who presses send

By default, you do. The system fills the employer's form in a visible window
and stops; there is no click anywhere in `pipeline/submit.py`, and a test fails
if one appears.

You can let it send on its own with `[autoapply] enabled = true`, and then one
rule decides: **it sends only when nothing had to be invented.** Every required
field must have been filled from your CV, your identity, or a reply you wrote
yourself under `[[answers]]` in `profile.toml`. A question you have not
answered, a CAPTCHA, an ambiguous submit button, a fit or ATS score below your
floor, a CV you have not read, the daily cap reached: any one of these stops it
and leaves the filled form open for you. Start with `rehearse = true`, which
runs every check and stops before the click.

```bash
python -m pipeline.autoapply --list       # what is eligible, and what blocks the rest
python -m pipeline.autoapply --rehearse <job_id>
```

The matching is callable headlessly too:

```bash
python match.py --file job.txt --compact
curl -X POST localhost:8770/api/v1/match -H 'Content-Type: application/json' -d '{"jd": "..."}'
```

## Why an LLM and not keywords

Real filenames from the collection this was built for:

| File | What it actually was |
|---|---|
| `CV_..._Data_Engineer_PFE.pdf` | an AI-agents / LangChain CV |
| `..._Resume-_Data_Engineer.pdf` | a generic data-science CV |
| `cv_s.pdf` | somebody else's CV entirely |
| `GARAAOUCH Souhaib.pdf` | a university project brief, not a CV |

Keyword rules get all four wrong. Reading the document gets them right.

## Requirements

- Linux with `systemd --user` (tested on Ubuntu)
- Python 3.11+
- `pdftotext` — `sudo apt install poppler-utils`
- `notify-send` for desktop notifications — `sudo apt install libnotify-bin`
- **Google Chrome or Chromium** — renders the tailored CV to PDF, and opens an
  employer's form when you ask it to. Playwright drives the Chrome you already
  have (`channel="chrome"`), so no browser is downloaded.
- A model, either:
  - **Claude Code** already installed and signed in — **no API key needed**, this
    is the default; or
  - **any API key**: Anthropic, OpenAI, Gemini, Mistral, Groq, DeepSeek,
    OpenRouter, a model running locally under Ollama, or anything else speaking
    the OpenAI chat-completions shape. Pick it in Réglages.

## Install

```bash
git clone https://github.com/<you>/cv-router.git
cd cv-router
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp config.example.toml config.toml       # paths and your name
cp pipeline.example.toml pipeline.toml   # the pipeline, if you want it
cp profile.example.toml profile.toml     # what goes on an employer's form

./.venv/bin/python indexer.py            # read your existing CVs
./install.sh                             # install the services
```

That installs three units: the watcher and the portal start immediately; the
pipeline timer is installed but left off, because it fetches job boards and
spends model calls. Turn it on when you mean to:

```bash
systemctl --user enable --now cv-router-pipeline.timer   # a cycle every 45 min
```

Then open <http://127.0.0.1:8770> and finish in **Réglages**.

### Configure

Open **Réglages** and set it there. Every field carries the sentence that
explains it, a value that would break the app is refused before it is written,
and the files keep their comments because only the line that changed is
rewritten.

Two things are not in the UI, because they are yours and stay out of git:

```bash
cp profile.example.toml profile.toml   # your name, contacts, links, answers
```

`profile.toml` holds what goes on an employer's form and the three links that
appear on every CV. Its `[[answers]]` section is the only source of answers to
form questions: a question with no entry of yours is one the system will not
answer, ever.

And the taxonomy, in `config.toml`:

```toml
[taxonomy.roles]                  # YOUR folders — invent whatever you need
"AI-ML-Engineering"    = "AI-ML-Engineer"
"Data-Engineering"     = "Data-Engineer"
"Software-Engineering" = "Software-Engineer"
```

The taxonomy is data, not code. The model is handed your folder names and picks
one per CV, so reshaping the filing system means editing TOML, not Python.

`[taxonomy.branches]` is a second axis — by default career stage, student vs
graduate — because the same specialty needs a different CV depending on whether
you are applying for an internship or a permanent job. Describe each branch in
terms of the **words a CV uses**, not dates: a graduate CV still lists the years
of its degree, and a model told to look at dates will misread that.

## Two knobs that measured worse than expected

Both exist, both are off by default, because on this collection the measurement
went against the intuition. Re-measure on yours before turning either on.

**A cheaper model for indexing** (`ai.index_model`). Summarising is an easier job
than classifying, so haiku ought to do. Measured over four CVs, one call each:

| | Latency | Student/graduate status kept |
|---|---|---|
| haiku | 12–19s | 3 of 4 |
| sonnet | 5–6s | 4 of 4 |

Haiku was slower *and* less reliable, so the default stays on `cli_model`.

**Several CVs per call** (`ai.index_batch_size`). Batching cuts the call count by
its factor, and on eight near-identical CVs one batched call took 46s against
143s for eight individual ones. But against those individual summaries as the
reference:

| | Skills overlap | Status kept |
|---|---|---|
| batch of 8, haiku | 69% | 6 of 8 |
| batch of 4, haiku | 71% | 6 of 8 |
| batch of 4, sonnet | 75% | 7 of 8 |

Summaries bleed between near-identical CVs, and two lost the student framing
entirely — one became "Deloitte HR transformation specialist". Since the index
exists to feed the portal's shortlist, and the shortlist weighs career stage
first, that trade is a bad one. Default is 1, i.e. off.

With four workers, indexing 90 CVs runs in a few minutes anyway, which is what
made batching unnecessary rather than merely unwise.

## How filing decides

A file is moved only when **all** of these hold:

- it is a CV — not a cover letter, a diploma, an invoice, a project brief
- it is **your** CV — someone else's is left alone
- confidence ≥ `min_confidence` (default 0.6)
- its content is new — a re-export of a CV you already have goes to
  `_Duplicates-auto/` instead

Anything else stays in Downloads, with the reason in the log and, optionally, a
notification. The tool never deletes anything.

Duplicate detection hashes the **extracted text**, not the bytes: two exports of
the same CV from the same builder have different bytes but identical text.

### What actually costs a model call

Not every download does. Everything decidable from the text alone is decided
first, so a call is only made for a PDF that is genuinely new:

| Downloaded | Model calls |
|---|---|
| a CV you don't have yet | 1 |
| a re-download of a CV already filed | 0 — matched on text signature |
| a scanned / image-only PDF | 0 — no text to send |
| a partial download (`.crdownload`, `.part`) | 0 |
| anything that isn't a PDF | 0 |
| a file you left in the folder, on later events | 0 — fingerprinted |
| a file you left in the folder, after a restart | 0 — verdicts persist |

So an idle watcher costs nothing, and re-exporting the same CV five times from a
CV builder costs one call, not five.

Verdicts are kept in `data/seen.json`, keyed on path + size + mtime and expiring
after `seen_ttl_days`. Without it, restarting the daemon re-classified everything
still sitting in the watch folder — a fresh call each time to reach last time's
conclusion. A dry run deliberately writes nothing there, so it can never make a
later real run skip a file.

Filenames come out as:

```
<Owner-Name>_<Role>_<Techno-or-Sector>_<FR|EN>[_n].pdf
```

## The portal

Paste a job ad, get back:

- the CV to send, and why, citing evidence from that CV
- the runner-up
- an estimated ATS score
- which required keywords the CV already covers, and which it misses
- **4–8 concrete edits** — current text, replacement text, which line of the ad
  it satisfies, ranked by priority
- red flags, and an opening line for a cover letter

Career stage is weighed first: a permanent role gets a graduate CV, an internship
gets the student one.

Matching runs in two passes so it stays cheap — a one-line-per-CV index picks a
shortlist of five, then only those five are read in full. Their extracted text
comes from the cache, and the index is re-read only when it actually changed.

`POST /api/match` with `{"job": "..."}` returns the same analysis as JSON.

## Reading the CV before it goes out

A tailored CV is a draft until you have read it. The editor beside it is the
document behind the PDF, not a text box: every field is editable, anything that
differs from your original is highlighted, and the A4 preview redraws as you
type with a line saying whether it still fits on one page.

- **Hide instead of delete.** A section, an entry or a single line can be taken
  off this CV with its text kept in the document. It is the quickest way back
  from two pages to one and, unlike deleting, reversible — so hiding is the
  plain gesture and deleting asks first.
- **Restructure.** Add and remove sections and entries, reorder them, edit the
  contact links that appear on every CV.
- **Choose the density,** or leave it to fit by itself.
- **Undo,** `Ctrl+Z`, twenty steps.

Nothing the model writes is free text: it may only replace wording it quotes
exactly from your CV, so it cannot invent experience. The PDF is read back with
`pdftotext` before it is used, the way an ATS reads it.

The file is named after the job, not after you:

```
Pigment_Data-Engineer-Growth-Team_Ada_LOVELACE_2026-09-23.pdf
```

Company first, because that is what you search for in a file picker, and the
role second, because two roles at one company must never share a name. Older
files move over with `python -m pipeline.tailor --rename`.

## Commands

| Command | What it does |
|---|---|
| `python indexer.py` | index new or changed CVs (incremental) |
| `python indexer.py --rebuild` | re-read the whole collection |
| `python indexer.py --limit 25 --sleep 2` | pace it, to stay under a plan limit |
| `python indexer.py --workers 1` | serial, if parallel calls trip a usage limit |
| `python indexer.py --batch 8` | several CVs per call — cheaper, less accurate |
| `python indexer.py --no-ai` | index from folder names only, no model calls |
| `python watcher.py --once` | sweep the watch folder now, then exit |
| `python watcher.py --dry-run` | decide and log, move nothing |
| `python portal.py` | run the portal in the foreground |
| `python test_routing.py` | filing logic, model stubbed |
| `python test_index_concurrency.py` | concurrent index writers lose nothing |
| `python test_pipeline.py` | the job pipeline — see PIPELINE.md |
| `python run_pipeline.py` | one full cycle: fetch, screen, evaluate, tailor |
| `python run_pipeline.py --no-fetch` | work through what is already collected |
| `python -m pipeline.tailor --rename` | move older CVs to the job-first name |
| `python -m pipeline.autoapply --list` | what could be sent, and what blocks the rest |
| `python -m pipeline.submit --next` | fill the best staged application's form |
| `python -m pipeline.tracker weekly` | response rate per fit bucket |
| `python -m pipeline.calibrate` | thresholds that reproduce your own labels |

Start with `--dry-run`: it prints every decision and its reasoning without
touching a file.

## Day to day

```bash
systemctl --user status cv-router-watcher
journalctl --user -u cv-router-watcher -f
tail -f data/cv-router.log
```

## Architecture

Three long-running processes, one shared library, no direct communication —
everything meets on the filesystem. The diagram below is the filing half; the
pipeline is a fourth, a timer firing `run_pipeline.py` every 45 minutes, and
**[PIPELINE.md](PIPELINE.md)** covers it.

```
   ~/Downloads                                  browser
        │                                          │
   ① inotify                                  ⑥ HTTP :8770
        ▼                                          ▼
 ┌──────────────┐                        ┌──────────────────┐
 │  watcher.py  │                        │    portal.py     │
 │   (daemon)   │                        │ (daemon, FastAPI)│
 └──────────────┘                        └──────────────────┘
        │                                          │
        └──────────► cvrouter.py ◄─────────────────┘
                   taxonomy · pdf                  ▲
                   index · AI · naming             │
                     │       │      │         indexer.py
              ②subprocess    │  ④notify-send  (on demand)
                     ▼       │      ▼
              claude -p      │   D-Bus ──► desktop notification
             (or the API)    │
                             │ ③ commit() under flock
                             ▼
                      data/index.json
                             ▲
                             │ ⑤ move / scan
              ~/Documents/CVs/…
```

**① The kernel pushes.** `watchdog` puts an inotify watch on the download folder.
Nothing polls.

**② The model call** is `claude -p --restricted --strict-mcp-config`, prompt on
stdin. `--restricted` disables every built-in tool, so text lifted out of an
unknown PDF is data and can never trigger an action. `CLAUDE_CODE_*` variables
are stripped so the call opens its own session.

**③ The index is the only shared state,** and every write merges. See below.

**④ Notifications** go over D-Bus. Failures are swallowed: no notifier must never
mean no filing.

**⑤ Files move, they are not copied,** which makes the whole thing idempotent —
a filed CV is no longer in Downloads to be filed again.

**⑥ The portal binds to localhost only.**

### The index merges, it never overwrites

Three processes write `data/index.json`. A plain load / mutate / save loses
entries — whoever saves last wins. Measured with four concurrent writers:
**33 of 100 entries survived.**

So there is no `save()`. Every write goes through `Index.commit()`:

1. take an exclusive `flock` on `data/index.lock`
2. **re-read** the file as it is now
3. merge the caller's records into that
4. write via a per-process temp file, then an atomic `replace()`

The re-read is inside the lock, so nothing can slip between it and the write.
Same test, four concurrent `commit()` writers: **100 of 100 survived.**

Readers take no lock — `replace()` is atomic, so a reader sees the old file or
the new one, never half of one.

`commit(prune=True)` drops entries whose PDF is gone, checking the **filesystem**
rather than the caller's snapshot, so a CV the watcher filed during a long
indexing run is never pruned.

## Your data never leaves your machine, except to the model

`config.toml`, `pipeline.toml`, `profile.toml`, `data/`, `applications/` and
your CVs are all gitignored. The API key lives in its own file, owner-readable
only, and is never printed back.

The only thing that leaves the machine is the text of a CV, or a job ad, sent
to whichever model you chose. Pick Ollama in Réglages and even that stays here.
If neither is acceptable for your documents, do not use this.

## Known limits

- **A site that detects bots will refuse an assisted fill, and it is right to.**
  The browser Playwright drives reports itself as automated. Nothing here hides
  that: the answer is the "Remplir à la main" panel, which hands you every value
  to paste into your own browser. Drop a host from
  `[submit] allowed_hosts` and that site goes back to manual for good.
- **Some job boards refuse any client that says what it is.** Rekrute answers
  `403 Access denied` unless the caller claims to be a browser, so it is not
  fetched. Paste the ad by hand instead; it enters the pipeline like any other.
- **Applying to many roles at one employer reads as spam,** whoever typed them.
  `[prefilter] max_per_company` caps how many are live at once.
- **Scanned PDFs are skipped.** Extraction is `pdftotext`; an image-only PDF
  yields nothing and stays in Downloads. Add OCR if you need it.
- **The CLI backend is slow** — 10–40s per call — and it consumes your Claude
  plan's usage allowance. Indexing 90 CVs is 90 calls, run `ai.index_workers` at
  a time (default 4). Drop to `--workers 1` if that trips a limit.
- The watcher watches the top level of the download folder, not subfolders.
- The web interface and the notification text are in French. Everything else —
  code, comments, config, prompts — is English.
- Linux only. The daemon, the notifications and the installer all assume
  `systemd --user` and D-Bus.

## License

MIT — see [LICENSE](LICENSE).
