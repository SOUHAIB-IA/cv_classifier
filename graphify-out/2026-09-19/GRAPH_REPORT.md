# Graph Report - cv-router  (2026-09-18)

## Corpus Check
- 27 files · ~25,555 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .in 4, .toml 3)

## Summary
- 381 nodes · 791 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7ee4d65a`
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
- Screener
- sources.py
- submit.py
- install.sh

## God Nodes (most connected - your core abstractions)
1. `DB` - 52 edges
2. `Index` - 23 edges
3. `PipelineConfig` - 18 edges
4. `Screener` - 18 edges
5. `Config` - 17 edges
6. `load_config()` - 16 edges
7. `main()` - 15 edges
8. `cv-router` - 14 edges
9. `match_job()` - 14 edges
10. `tailor_job()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `load_config()`  [EXTRACTED]
  match.py → cvrouter.py
- `match_job()` --calls--> `AIError`  [EXTRACTED]
  matcher.py → cvrouter.py
- `match_job()` --calls--> `ask_json()`  [EXTRACTED]
  matcher.py → cvrouter.py
- `match_job()` --calls--> `Index`  [EXTRACTED]
  matcher.py → cvrouter.py
- `match_job()` --calls--> `pdf_text_cached()`  [EXTRACTED]
  matcher.py → cvrouter.py

## Import Cycles
- None detected.

## Communities (13 total, 2 thin omitted)

### Community 0 - "Index"
Cohesion: 0.13
Nodes (18): CVRecord, Index, IndexLockTimeout, load_config(), Ada', 'LOVELACE' -> 'Ada-LOVELACE' (filename prefix)., One line for the stage-1 matching prompt — keeps tokens small., The shared CV index. Three processes touch this file — the watcher, the indexer…, Merge changes into whatever is on disk right now, under a lock. prune=True also… (+10 more)

### Community 1 - "Router"
Cohesion: 0.16
Nodes (9): FileSystemEventHandler, Handler, main(), Path, Background daemon: watch the Downloads folder and file every CV PDF that lands…, The verdict reached for this exact file before, if any., Persist a verdict — never from a dry run, which must leave no trace that would…, Wait until the file stops growing, so we don't read a partial download. (+1 more)

### Community 2 - "test_pipeline.py"
Cohesion: 0.10
Nodes (19): dedupe_key(), _norm(), company + title, normalised so a re-post or a cross-post collides., check(), fake_match(), job(), main(), counted() (+11 more)

### Community 3 - "cvrouter.py"
Cohesion: 0.07
Nodes (44): AIError, ascii_fold(), _ask_api(), _ask_cli(), ask_json(), _cache_key(), classify_pdf(), Config (+36 more)

### Community 4 - "match_job"
Cohesion: 0.12
Nodes (24): get, main(), Headless matcher: a job description in, the best CV and its edits out, as JSON.…, _clamp(), guess_language(), match_job(), Config, Index (+16 more)

### Community 5 - "DB"
Cohesion: 0.06
Nodes (52): best_thresholds(), _decide(), label(), main(), Calibrate the fit-score thresholds against your own judgement. python -m…, Every (auto, review) pair scored by agreement with your labels. Ties are broken…, report(), _abs() (+44 more)

### Community 6 - "tailor.py"
Cohesion: 0.08
Nodes (49): PipelineConfig, decide(), evaluate(), Config, candidate -> matched, through cv-router, within the daily budget. Best pre-…, One routing pass. A dry run rehearses every stage on an in-memory copy of the…, 2-.../AI-ML-Engineering/Souhaib-GARAAOUCH_AI-ML-Engineer_MLOps-LLM_EN.pdf' ->…, sourced -> filtered | candidate. Free: no model calls. Waiting candidates are… (+41 more)

### Community 7 - "cv-router"
Cohesion: 0.07
Nodes (26): Components, Guard rails, Job application pipeline, Measuring success, Quick start, Tailoring: what may change, what may not, Tests, What the first real run showed (+18 more)

### Community 9 - "Screener"
Cohesion: 0.13
Nodes (17): _junk_re(), Pattern, _location_rank(), Candidates that do not earn an evaluation. - the same role posted several times…, Lower is better: the position, in location_include, of the first term the…, triage(), _fold(), Config (+9 more)

### Community 10 - "sources.py"
Cohesion: 0.15
Nodes (17): Client, HTMLParser, ashby(), client(), _date(), greenhouse(), lever(), _pretty() (+9 more)

### Community 11 - "submit.py"
Cohesion: 0.31
Nodes (10): fill_form(), _identity(), main(), Path, Application Submission Assistant — stage an application; you submit it. python…, Fill what is safe to fill. Returns a report — names only, no values., _record(), staged() (+2 more)

## Knowledge Gaps
- **22 isolated node(s):** `Quick start`, `Components`, `Where this departs from the spec, and why`, `Tailoring: what may change, what may not`, `Guard rails` (+17 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 140 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `DB` connect `DB` to `Screener`, `test_pipeline.py`, `submit.py`, `tailor.py`?**
  _High betweenness centrality (0.192) - this node is a cross-community bridge._
- **Why does `Index` connect `Index` to `test_pipeline.py`, `cvrouter.py`, `match_job`, `tailor.py`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `main()` connect `test_pipeline.py` to `Index`, `match_job`, `DB`, `Screener`, `sources.py`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Are the 20 inferred relationships involving `DB` (e.g. with `label()` and `report()`) actually correct?**
  _`DB` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Screener` (e.g. with `_location_rank()` and `screen()`) actually correct?**
  _`Screener` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Quick start`, `Components`, `Where this departs from the spec, and why` to the rest of the system?**
  _22 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Index` be split into smaller, more focused modules?**
  _Cohesion score 0.1282051282051282 - nodes in this community are weakly interconnected._