# cv-router

If you tailor your CV per application, you end up with eighty near-identical
PDFs called `resume-3 (2).pdf` and no idea which one to send.

cv-router fixes both halves of that:

- **A watcher** files every CV you download into the right folder, renamed, with
  no action from you.
- **A portal** takes a job ad and tells you which CV to send and what to change
  before you send it.

An LLM reads the whole document — profile, skills, projects — so it does not get
fooled by a filename or a stale job title at the top of the page.

```
~/Downloads/resume-3 (2).pdf
        │
        ▼   read, classified, renamed, moved
~/Documents/CVs/2-Graduate/AI-ML-Engineering/
        Ada-LOVELACE_AI-ML-Engineer_RAG-MLOps_EN.pdf
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
- An LLM, either:
  - **Claude Code** already installed and signed in — **no API key needed**, this
    is the default; or
  - an Anthropic API key, billed separately.

## Install

```bash
git clone https://github.com/<you>/cv-router.git
cd cv-router
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp config.example.toml config.toml   # then edit it — see below
./.venv/bin/python indexer.py        # read your existing CVs
./install.sh                         # start both services
```

Portal: <http://127.0.0.1:8770>

### Configure

Everything lives in `config.toml`. The parts you must set:

```toml
[paths]
cv_root   = "~/Documents/CVs"     # where sorted CVs go
watch_dir = "~/Downloads"         # what to watch

[behaviour]
owner_name    = "Ada"             # so someone else's CV is never filed as yours
owner_surname = "LOVELACE"

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
shortlist of five, then only those five are read in full.

`POST /api/match` with `{"job": "..."}` returns the same analysis as JSON.

## Commands

| Command | What it does |
|---|---|
| `python indexer.py` | index new or changed CVs (incremental) |
| `python indexer.py --rebuild` | re-read the whole collection |
| `python indexer.py --limit 25 --sleep 2` | pace it, to stay under a plan limit |
| `python indexer.py --no-ai` | index from folder names only, no model calls |
| `python watcher.py --once` | sweep the watch folder now, then exit |
| `python watcher.py --dry-run` | decide and log, move nothing |
| `python portal.py` | run the portal in the foreground |
| `python test_routing.py` | filing logic, model stubbed |
| `python test_index_concurrency.py` | concurrent index writers lose nothing |

Start with `--dry-run`: it prints every decision and its reasoning without
touching a file.

## Day to day

```bash
systemctl --user status cv-router-watcher
journalctl --user -u cv-router-watcher -f
tail -f data/cv-router.log
```

## Architecture

Three processes, one shared library, no direct communication — everything meets
on the filesystem.

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

`config.toml`, `data/` and your CVs are all gitignored. The only thing that goes
out is the text of a CV, or a job ad you paste, sent to Anthropic for the call.
If that is not acceptable for your documents, do not use this.

## Known limits

- **Scanned PDFs are skipped.** Extraction is `pdftotext`; an image-only PDF
  yields nothing and stays in Downloads. Add OCR if you need it.
- **The CLI backend is slow** — 10–40s per call — and it consumes your Claude
  plan's usage allowance. One download is one call; indexing 90 CVs is 90.
- The watcher watches the top level of the download folder, not subfolders.
- The portal UI and the notification text are in French. Everything else — code,
  comments, config, prompts — is English.
- Linux only. The daemon, the notifications and the installer all assume
  `systemd --user` and D-Bus.

## License

MIT — see [LICENSE](LICENSE).
