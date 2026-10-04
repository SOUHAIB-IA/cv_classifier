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

## Six pages

Everything is one local web app on <http://127.0.0.1:8770>. `Ctrl+K` searches
every posting from any of them. A first run opens `/bienvenue` instead, which
explains what the tool does and carries the three steps it needs from you.

| | |
|---|---|
| **Analyser** | paste an ad, get the CV to send and what to change first |
| **Pipeline** | the journey of a posting, what is waiting for you, and the graphs |
| **Données** | every posting ever seen: search, filter, sort, export as CSV |
| **Canada** | paste a Canadian ad, get a Canadian-format resume and what changed |
| **Réglages** | every setting, with the sentence that explains it |
| **Avis** | opens the feedback form, because what broke for you is worth knowing |

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

- Linux, macOS or Windows. There is no service to install: `python start.py`
  runs the watcher and the web app together in one process.
- Python 3.11+
- **poppler** (`pdftotext`, `pdfinfo`), which reads your PDFs:
  `sudo apt install poppler-utils`, `brew install poppler`, or the
  [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
  build added to your PATH.
- Desktop notifications work out of the box on all three: `notify-send` on
  Linux (`sudo apt install libnotify-bin`), osascript on macOS, PowerShell on
  Windows.
- **Google Chrome or Chromium** — renders the tailored CV to PDF, and opens an
  employer's form when you ask it to. Playwright drives the Chrome you already
  have (`channel="chrome"`), so no browser is downloaded.
- A model, either:
  - **any API key**, which is the default: Anthropic, OpenAI, Gemini, Mistral,
    Groq, DeepSeek,
    OpenRouter, a model running locally under Ollama, or anything else speaking
    the OpenAI chat-completions shape. Pick it in Réglages; or
  - **Claude Code** already installed and signed in, which needs no key but
    needs a Claude subscription.

## Install

```bash
git clone https://github.com/<you>/cv-router.git
cd cv-router
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

./.venv/bin/python start.py
```

That is the whole installation. The first run writes its own settings files,
opens the welcome page, and walks you through the three things it needs: your
name, a model, and the folder your CVs are in. Reading the collection is a
button on that page, not a command.

### Configure

Everything is set on the pages themselves. Each field carries the sentence that
explains it, a value that would break the app is refused before it is written,
and the files keep their comments because only the line that changed is
rewritten. The watcher rereads them when you save, so a setting takes effect
without going back to the terminal.

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

## Canada Resume Studio

A separate module for Canadian-format resumes, in `canada_module/`. It reads the
CV index and the shared rendering helpers; it never writes to the index, never
touches the pipeline database, and puts nothing where the watcher looks. The
watcher observes `watch_dir` non-recursively, so output under
`canada_module/output/` is out of its reach by construction, not by convention.

```bash
cp canada_module/canada.example.toml canada_module/canada.toml   # optional
.venv/bin/python -m canada_module rules                          # what loaded
.venv/bin/python -m canada_module check --role de --lang en      # lint a CV
.venv/bin/python -m canada_module convert --role de --lang en    # make it Canadian
.venv/bin/python -m canada_module tailor ad.txt --company Shopify --city "Toronto, ON"
```

Or open the **Canada** tab and paste an ad.

### What it does

**Checks.** Lints a PDF or a structured document against the rules and reports
what it cannot verify instead of counting it as a pass: a PDF carries no table
semantics and only an estimate of font size, so those are listed as unchecked.
Run against this collection it finds A4 paper and an embedded photo on all
twelve role CVs, plus `modeling` where Canadian English wants `modelling`.

**Converts.** Re-spells, reformats dates to `Mon YYYY`, reorders sections,
drops what Canadian rules exclude, and renders US Letter in one column, with a
`.docx` beside the PDF. Every change is logged with the rule behind it.

**Tailors.** Given an ad, picks the role and the language, scores the keyword
overlap, and reorders — your skills groups, the items inside them, the bullets,
the sentences of the summary — so what the ad asks about reads first.

### What it will not do

It only reorders and reformats. It never writes a sentence, and a term the ad
asks for that your CV does not have is reported as a gap and never inserted.
Where a claim has no figure behind it the result is a `[METRIC?]` placeholder
listed in the report, never an invented number. A bullet opening with
"Responsible for" is flagged rather than rewritten, because turning it into an
achievement needs a fact the bullet does not carry. And a bullet that opens by
referring back to the one above it is never promoted, since "Built the delivery
chain around it" reads as nonsense in first position.

`config.py` refuses to write "eligible to work in Canada" unless you set
`authorized_to_work = true` yourself, and leaves the Canadian equivalence of a
Moroccan engineering degree blank, because only an assessing body can state it.

### The rules are a file, not code

`canada_module/canada_rules.yaml` holds every rule with its source, and
`RESEARCH.md` holds the quotation behind each one, ranked: government sources
(Job Bank, Québec.ca, the OQLF, the Portail linguistique du Canada), university
career centres (UBC, U of T Mississauga), ATS vendor documentation (Greenhouse,
Workday), and nothing from a resume blog. Five widely repeated claims did not
survive a primary source and are corrected there — among them that Canadian
English is `-ize` and `-yze`, not `-ise`, so `analyze` and `optimize` were
already right and `programme` would have been wrong.

`canada_module/keywords.yaml` is the technical vocabulary the match score is
computed over. Grow it as you read more postings.

Loading refuses a `checks:` entry naming a check the linter does not implement,
because a typo there would look like a rule that passes.

## Start it

```bash
python start.py
```

One command, one window, on Linux, macOS or Windows. The watcher runs in a
background thread and the web app in the main one, so there is no service to
install. Prerequisites are checked first and a missing one is reported as the
sentence you need, which package to install, rather than as a traceback three
minutes later.

**The first run writes its own settings files** from the examples beside them,
opens `/bienvenue`, and does not start the watcher. That page explains what the
tool does and gives the three steps it needs, each next to the button that
settles it: your name and a model, reading your CVs, and a first job ad.
Nothing is filed until the first two are done. That is deliberate: without a model the watcher can only fail, once
per PDF in the folder it watches, and the first person to run this outside the
machine it was written on watched exactly that happen.

| Flag | What it does |
|---|---|
| `--no-watcher` | the web app only, leave the download folder alone |
| `--dry-run` | the watcher decides and logs, but moves nothing |
| `--no-browser` | do not open a window |
| `--port 8771` | somewhere other than the configured port |

`install.sh` is still there for the systemd services on Linux, and is now
optional: it buys you start-on-login, nothing else.

### The watcher is driven from the page

The watcher reads the settings once, when it starts, so a setting changed while
it runs would not reach it. The **Pour commencer** tab carries a panel that
says whether it is running and on which folder, with Start, Stop and Restart.
Saving a setting restarts it for you, so what the page says and what the
watcher does cannot drift apart.

It is the same process throughout: `python start.py` runs the watcher in a
thread beside the web app, and the panel talks to that thread. Started any
other way, the panel says it is not in charge rather than pretending to drive
something it cannot reach. The old button called `systemctl --user restart`,
which exists only if you ran `install.sh` and never existed at all on Windows
or macOS; that path is still there for the people who installed the services.

### Running on Windows and macOS

The locking goes through portalocker (`flock` on Unix, `LockFileEx` on Windows)
and the folder watching through watchdog, which picks inotify, FSEvents or
ReadDirectoryChangesW by itself. `test_portable.py` holds the line: it fails if
any file imports a module the standard library ships only on Unix, which is the
defect that made this Linux-only in the first place — `fcntl` at the top of two
modules, so on Windows nothing ran at all.

The desktop gestures go through `desktop.py`, which knows the three ways to make
each one: a notification through `notify-send`, `osascript` or a PowerShell
balloon; showing a file through `FileManager1.ShowItems`, `open -R` or
`explorer /select,`. None of them is essential, so each returns False rather
than raising — a notification that does not appear must not stop the watcher
from filing a CV. `test_portable.py` fails if any module outside `desktop.py`
calls one of those tools directly.

The one button that did not survive the move is "restart the watcher". It
existed because the watcher was a systemd service; started with `start.py` it is
a thread inside the application, so the button now says to stop with Ctrl+C and
start again rather than calling systemctl at something that is not there.

Every push runs the suites on **ubuntu-latest, windows-latest and
macos-latest** (`.github/workflows/tests.yml`). That is the point of the
workflow: the defect that made this Linux-only is invisible on the machine you
develop on, so it needs a runner that is not yours.

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
| `python -m canada_module rules` | the Canada rules and config in force |
| `python -m canada_module check --role de` | lint a role CV against the Canada rules |
| `python -m canada_module convert --role de` | build the Canadian version of it |
| `python -m canada_module tailor ad.txt` | tailor it to one posting |
| `python canada_module/tests/test_checker.py` | the Canada linter |
| `python canada_module/tests/test_converter.py` | the Canada converter |
| `python canada_module/tests/test_customize.py` | the customizer and its page |
| `python test_portable.py` | the lock, the launcher, finding Chrome, no Unix-only imports |

Start with `--dry-run`: it prints every decision and its reasoning without
touching a file.

## Day to day

The watcher says whether it is running, and on which folder, in the panel at the
top of **Réglages**, where you can also stop and restart it. The log is the same
on every system:

```bash
tail -f data/cv-router.log
```

Installed as a systemd service with `install.sh`, it also answers to:

```bash
systemctl --user status cv-router-watcher
journalctl --user -u cv-router-watcher -f
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

**Windows passes, and nobody has used it there.** All four CI jobs are green,
including `windows-latest`: no Unix-only import, the lock taken and released
through `LockFileEx`, Chrome found, `start.py` serving every page, and every
suite passing. What that does not prove is a day of real use on a real Windows
desktop, which has not happened yet. poppler is also the one prerequisite
Windows has no installer for: you download a build and put it on your PATH.


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
- **The interface is desktop first.** Below roughly 700px the navigation bar
  crushes rather than wrapping. It stays usable, it does not stay pretty, and
  nothing here is meant to be driven from a phone.

## License and what you are responsible for

[PolyForm Noncommercial 1.0.0](LICENSE). Use it, change it, share it, for any
noncommercial purpose: your own job hunt, study, research, a hobby. Selling it,
hosting it as a paid service, or putting it inside something you sell needs
written permission first. Ask.

This is not an OSI open source licence, and that is the deliberate trade: the
source is yours to read and run, the commercial rights are not.

Commits published before this change were released under MIT, and that grant
cannot be withdrawn for the versions that carried it.

### What it will not do, and what is yours to carry

It fills an employer's form and stops. It does not send on your behalf unless
you turn that on yourself, and even then it refuses whenever a question is
unanswered or the submit button is ambiguous. Everything that reaches an
employer is your application, in your name, and you are responsible for what it
says.

Your CVs stay on your machine. The one thing that leaves it is the text of the
job ad and of the CVs being compared, sent to whichever model provider you
configured, under that provider's own terms. Choose Ollama if you want nothing
to leave at all.

The software comes as is, with no warranty. See the No Liability section of the
licence.
