# Graph Report - cv-router  (2026-09-19)

## Corpus Check
- 31 files · ~33,134 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 12 file(s) not represented in the graph (top: (none) 4, .in 4, .toml 3)

## Summary
- 477 nodes · 971 edges · 24 communities (14 shown, 10 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.9)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0514c30f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Index
- Router
- test_pipeline.py
- cvrouter.py
- portal.py
- DB
- tailor.py
- cv-router
- SeenStore
- Screener
- PipelineConfig
- orchestrate.py
- install.sh
- webui.py
- job.js
- common.js
- dashboard.js
- get
- post
- Request
- Index
- sources.py
- Config
- DB

## God Nodes (most connected - your core abstractions)
1. `DB` - 48 edges
2. `Index` - 24 edges
3. `PipelineConfig` - 17 edges
4. `main()` - 17 edges
5. `Config` - 17 edges
6. `load_config()` - 17 edges
7. `load()` - 16 edges
8. `tailor_job()` - 16 edges
9. `match_job()` - 14 edges
10. `cv-router` - 14 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `load()`  [EXTRACTED]
  test_pipeline.py → pipeline/config.py
- `setup()` --calls--> `load()`  [EXTRACTED]
  test_pipeline.py → pipeline/config.py
- `_ctx()` --calls--> `load()`  [EXTRACTED]
  webui.py → pipeline/config.py
- `job_preview()` --calls--> `load()`  [EXTRACTED]
  webui.py → pipeline/config.py
- `structured()` --calls--> `content_sig()`  [EXTRACTED]
  pipeline/tailor.py → cvrouter.py

## Import Cycles
- None detected.

## Communities (24 total, 10 thin omitted)

### Community 1 - "Router"
Cohesion: 0.15
Nodes (9): FileSystemEventHandler, Handler, main(), Path, Background daemon: watch the Downloads folder and file every CV PDF that lands…, The verdict reached for this exact file before, if any., Persist a verdict — never from a dry run, which must leave no trace that would…, Wait until the file stops growing, so we don't read a partial download. (+1 more)

### Community 2 - "test_pipeline.py"
Cohesion: 0.11
Nodes (16): check(), fake_match(), job(), main(), counted(), Tests for the job pipeline. Self-contained: temp database, no network, the…, setup(), check() (+8 more)

### Community 3 - "cvrouter.py"
Cohesion: 0.07
Nodes (52): AIError, ascii_fold(), _ask_api(), _ask_cli(), ask_json(), _cache_key(), classify_pdf(), Config (+44 more)

### Community 4 - "portal.py"
Cohesion: 0.24
Nodes (14): analyse(), api_cvs(), api_match(), api_v1_match(), home(), _index(), match(), get (+6 more)

### Community 5 - "DB"
Cohesion: 0.05
Nodes (60): best_thresholds(), _decide(), label(), main(), Calibrate the fit-score thresholds against your own judgement. python -m…, Every (auto, review) pair scored by agreement with your labels. Ties are broken…, report(), _abs() (+52 more)

### Community 6 - "tailor.py"
Cohesion: 0.08
Nodes (55): Config, DB, PipelineConfig, apply_edits(), attach_links(), coverage(), cv_paths(), doc_text() (+47 more)

### Community 7 - "cv-router"
Cohesion: 0.07
Nodes (26): Components, Guard rails, Job application pipeline, Measuring success, Quick start, Tailoring: what may change, what may not, Tests, What the first real run showed (+18 more)

### Community 9 - "Screener"
Cohesion: 0.16
Nodes (13): _junk_re(), Pattern, _fold(), Config, Index, Free first-pass screening: decides which jobs deserve a model evaluation. A…, Whole-word match; a trailing * makes it a prefix. Plain substrings are useless…, Split a location into places, and whether it is remote at all. The work mode is… (+5 more)

### Community 11 - "orchestrate.py"
Cohesion: 0.14
Nodes (24): Index, Path, One pipeline run at a time. A second scheduled run exits instead of racing the…, run_lock(), decide(), evaluate(), evaluate_job(), _location_rank() (+16 more)

### Community 13 - "webui.py"
Cohesion: 0.14
Nodes (28): get, post, Request, add_job(), _ctx(), cv_pdf(), dashboard(), _guard() (+20 more)

### Community 14 - "job.js"
Cohesion: 0.19
Nodes (21): baseAt(), differs(), field(), getAt(), load(), norm(), origHint(), renderEditor() (+13 more)

### Community 16 - "dashboard.js"
Cohesion: 0.39
Nodes (6): evText(), fillQueue(), refresh(), row(), start(), TH

### Community 20 - "Index"
Cohesion: 0.10
Nodes (19): CVRecord, Index, IndexLockTimeout, load_config(), Ada', 'LOVELACE' -> 'Ada-LOVELACE' (filename prefix)., One line for the stage-1 matching prompt — keeps tokens small., The shared CV index. Three processes touch this file — the watcher, the indexer…, Snapshot for reading. Readers need no lock — writes land atomically. (+11 more)

### Community 21 - "sources.py"
Cohesion: 0.15
Nodes (17): Client, HTMLParser, ashby(), client(), _date(), greenhouse(), lever(), _pretty() (+9 more)

## Knowledge Gaps
- **26 isolated node(s):** `TH`, `reverted`, `install.sh script`, `STATUS_FR`, `TH` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 176 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DB` connect `DB` to `test_pipeline.py`, `orchestrate.py`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `Index` connect `Index` to `orchestrate.py`, `test_pipeline.py`, `cvrouter.py`, `portal.py`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `main()` connect `test_pipeline.py` to `cvrouter.py`, `DB`, `Screener`, `Index`, `sources.py`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 19 inferred relationships involving `DB` (e.g. with `label()` and `report()`) actually correct?**
  _`DB` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `main()` (e.g. with `boom()` and `counted()`) actually correct?**
  _`main()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `TH`, `reverted`, `install.sh script` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_pipeline.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11076923076923077 - nodes in this community are weakly interconnected._