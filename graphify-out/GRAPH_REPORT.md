# Graph Report - cv-router  (2026-09-19)

## Corpus Check
- 31 files · ~31,510 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 4, .in 4, .toml 3)

## Summary
- 464 nodes · 954 edges · 20 communities (14 shown, 6 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 45 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `066c8054`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Index
- Router
- test_pipeline.py
- cvrouter.py
- match_job
- DB
- tailor.py
- cv-router
- SeenStore
- config.py
- fetch.py
- orchestrate.py
- install.sh
- webui.py
- job.js
- common.js
- dashboard.js
- get
- post
- Request

## God Nodes (most connected - your core abstractions)
1. `DB` - 60 edges
2. `Index` - 24 edges
3. `Config` - 17 edges
4. `load_config()` - 17 edges
5. `main()` - 16 edges
6. `tailor_job()` - 14 edges
7. `match_job()` - 14 edges
8. `load()` - 14 edges
9. `cv-router` - 14 edges
10. `Router` - 13 edges

## Surprising Connections (you probably didn't know these)
- `_rows()` --uses--> `DB`  [INFERRED]
  webui.py → pipeline/db.py
- `main()` --calls--> `dedupe_key()`  [EXTRACTED]
  test_pipeline.py → pipeline/db.py
- `cycle()` --calls--> `DB`  [EXTRACTED]
  run_pipeline.py → pipeline/db.py
- `main()` --calls--> `DB`  [EXTRACTED]
  test_pipeline.py → pipeline/db.py
- `_ctx()` --calls--> `DB`  [EXTRACTED]
  webui.py → pipeline/db.py

## Import Cycles
- None detected.

## Communities (20 total, 6 thin omitted)

### Community 0 - "Index"
Cohesion: 0.10
Nodes (19): CVRecord, Index, IndexLockTimeout, load_config(), Ada', 'LOVELACE' -> 'Ada-LOVELACE' (filename prefix)., One line for the stage-1 matching prompt — keeps tokens small., The shared CV index. Three processes touch this file — the watcher, the indexer…, Snapshot for reading. Readers need no lock — writes land atomically. (+11 more)

### Community 1 - "Router"
Cohesion: 0.15
Nodes (9): FileSystemEventHandler, Handler, main(), Path, Background daemon: watch the Downloads folder and file every CV PDF that lands…, The verdict reached for this exact file before, if any., Persist a verdict — never from a dry run, which must leave no trace that would…, Wait until the file stops growing, so we don't read a partial download. (+1 more)

### Community 2 - "test_pipeline.py"
Cohesion: 0.11
Nodes (16): check(), fake_match(), job(), main(), counted(), Tests for the job pipeline. Self-contained: temp database, no network, the…, setup(), check() (+8 more)

### Community 3 - "cvrouter.py"
Cohesion: 0.08
Nodes (44): AIError, ascii_fold(), _ask_api(), _ask_cli(), ask_json(), _cache_key(), classify_pdf(), Config (+36 more)

### Community 4 - "match_job"
Cohesion: 0.12
Nodes (24): main(), Headless matcher: a job description in, the best CV and its edits out, as JSON.…, _clamp(), guess_language(), match_job(), Config, Index, Headless job matching: a job description in, the best CV and its edits out.… (+16 more)

### Community 5 - "DB"
Cohesion: 0.06
Nodes (43): best_thresholds(), _decide(), label(), main(), Calibrate the fit-score thresholds against your own judgement. python -m…, Every (auto, review) pair scored by agreement with your labels. Ties are broken…, report(), DB (+35 more)

### Community 6 - "tailor.py"
Cohesion: 0.09
Nodes (47): apply_edits(), coverage(), cv_paths(), doc_text(), _fields(), find_chrome(), html_to_pdf(), _in_protected() (+39 more)

### Community 7 - "cv-router"
Cohesion: 0.07
Nodes (26): Components, Guard rails, Job application pipeline, Measuring success, Quick start, Tailoring: what may change, what may not, Tests, What the first real run showed (+18 more)

### Community 9 - "config.py"
Cohesion: 0.12
Nodes (19): Pattern, _abs(), load(), load_profile(), PipelineConfig, Path, Pipeline configuration: pipeline.toml (behaviour) and profile.toml (you).…, Your identity for form pre-fill, merged with the per-track account. Returns… (+11 more)

### Community 10 - "fetch.py"
Cohesion: 0.10
Nodes (25): Client, HTMLParser, add_manual(), due_boards(), fetch(), main(), parse_board(), Job Sourcing Service — pull postings from the configured company boards. python… (+17 more)

### Community 11 - "orchestrate.py"
Cohesion: 0.12
Nodes (27): Index, Path, One pipeline run at a time. A second scheduled run exits instead of racing the…, run_lock(), decide(), evaluate(), evaluate_job(), _location_rank() (+19 more)

### Community 13 - "webui.py"
Cohesion: 0.15
Nodes (27): add_job(), _ctx(), cv_pdf(), dashboard(), _guard(), job_data(), job_evaluate(), job_page() (+19 more)

### Community 14 - "job.js"
Cohesion: 0.18
Nodes (21): baseAt(), differs(), field(), getAt(), load(), norm(), origHint(), renderEditor() (+13 more)

### Community 16 - "dashboard.js"
Cohesion: 0.39
Nodes (6): evText(), fillQueue(), refresh(), row(), start(), TH

## Knowledge Gaps
- **26 isolated node(s):** `STATUS_FR`, `TH`, `TH`, `reverted`, `install.sh script` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 168 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DB` connect `DB` to `test_pipeline.py`, `tailor.py`, `fetch.py`, `orchestrate.py`, `webui.py`?**
  _High betweenness centrality (0.193) - this node is a cross-community bridge._
- **Why does `Index` connect `Index` to `orchestrate.py`, `test_pipeline.py`, `cvrouter.py`, `match_job`?**
  _High betweenness centrality (0.077) - this node is a cross-community bridge._
- **Why does `main()` connect `test_pipeline.py` to `Index`, `cvrouter.py`, `match_job`, `DB`, `config.py`, `fetch.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `DB` (e.g. with `label()` and `report()`) actually correct?**
  _`DB` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `main()` (e.g. with `boom()` and `counted()`) actually correct?**
  _`main()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `STATUS_FR`, `TH`, `TH` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Index` be split into smaller, more focused modules?**
  _Cohesion score 0.10037878787878787 - nodes in this community are weakly interconnected._