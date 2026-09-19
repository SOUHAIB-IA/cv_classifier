# Graph Report - cv-router  (2026-09-16)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 141 nodes · 265 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 7 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a96b1283`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Index
- Router
- main
- main
- portal.py
- Config
- Path
- cvrouter.py
- SeenStore
- classify_pdf
- pdf_text_cached
- notify
- install.sh

## God Nodes (most connected - your core abstractions)
1. `Index` - 19 edges
2. `Config` - 17 edges
3. `Router` - 13 edges
4. `load_config()` - 12 edges
5. `main()` - 11 edges
6. `main()` - 10 edges
7. `CVRecord` - 9 edges
8. `pdf_text_cached()` - 9 edges
9. `build_record()` - 9 edges
10. `SeenStore` - 8 edges

## Surprising Connections (you probably didn't know these)
- `build_record()` --references--> `CVRecord`  [EXTRACTED]
  indexer.py → cvrouter.py
- `main()` --calls--> `Index`  [EXTRACTED]
  indexer.py → cvrouter.py
- `_index()` --calls--> `Index`  [EXTRACTED]
  portal.py → cvrouter.py
- `main()` --calls--> `Index`  [EXTRACTED]
  test_routing.py → cvrouter.py
- `analyse()` --calls--> `AIError`  [EXTRACTED]
  portal.py → cvrouter.py

## Import Cycles
- None detected.

## Communities (13 total, 3 thin omitted)

### Community 0 - "Index"
Cohesion: 0.12
Nodes (17): CVRecord, Index, load_config(), Ada', 'LOVELACE' -> 'Ada-LOVELACE' (filename prefix)., One line for the stage-1 matching prompt — keeps tokens small., The shared CV index. Three processes touch this file — the watcher, the indexer…, Snapshot for reading. Readers need no lock — writes land atomically., Merge changes into whatever is on disk right now, under a lock. prune=True also… (+9 more)

### Community 1 - "Router"
Cohesion: 0.15
Nodes (9): FileSystemEventHandler, Handler, main(), Path, Background daemon: watch the Downloads folder and file every CV PDF that lands…, The verdict reached for this exact file before, if any., Persist a verdict — never from a dry run, which must leave no trace that would…, Wait until the file stops growing, so we don't read a partial download. (+1 more)

### Community 2 - "main"
Cohesion: 0.17
Nodes (9): check(), main(), End-to-end test of the filing logic with the model call stubbed out. Self-…, make_pdf(), Path, Test helpers: a throwaway config and a real-enough PDF. The tests must not…, Write a minimal one-page PDF whose text pdftotext can extract., A Config pointing at fresh temp dirs. Caller removes the returned dir. (+1 more)

### Community 3 - "main"
Cohesion: 0.22
Nodes (13): headline_of(), _junk_re(), The tagline under the name — usually line 2 of the PDF., branch_and_specialty(), build_record(), main(), _ask(), summarise_batch() (+5 more)

### Community 4 - "portal.py"
Cohesion: 0.27
Nodes (12): get, analyse(), api_cvs(), api_match(), home(), _index(), match(), POST {"job": "...'} -> the same analysis as JSON, for scripting. (+4 more)

### Community 5 - "Config"
Cohesion: 0.33
Nodes (8): AIError, _ask_api(), _ask_cli(), ask_json(), Config, IndexLockTimeout, One-shot call that must come back as a JSON object. `model` overrides the…, RuntimeError

### Community 6 - "Path"
Cohesion: 0.28
Nodes (7): destination(), find_claude_bin(), Path, Newest Claude Code binary on this machine, or None., Where a classified CV belongs, and what it should be called., unique_name(), _vkey()

### Community 7 - "cvrouter.py"
Cohesion: 0.29
Nodes (7): ascii_fold(), prune_text_cache(), Core library for cv-router: config, PDF text, the CV index, and the AI calls.…, Drop cache entries untouched for a while. Returns how many went., setup_logging(), slug(), Logger

### Community 9 - "classify_pdf"
Cohesion: 0.33
Nodes (6): classify_pdf(), content_sig(), pdf_text(), Extract text with pdftotext. Returns '' on any failure., Whitespace/case-insensitive signature — catches re-exports of one CV., Ask the model to place one PDF. Pass `text` if you already extracted it, so a…

### Community 10 - "pdf_text_cached"
Cohesion: 0.50
Nodes (4): _cache_key(), pdf_text_cached(), Identity of a file's bytes, cheap to compute: path + size + mtime., pdf_text() with an on-disk cache. Extraction spawns a pdftotext process and is…

## Knowledge Gaps
- **1 isolated node(s):** `install.sh script`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 48 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Index` connect `Index` to `main`, `main`, `portal.py`, `Path`, `cvrouter.py`?**
  _High betweenness centrality (0.179) - this node is a cross-community bridge._
- **Why does `Config` connect `Config` to `Index`, `Router`, `main`, `main`, `Path`, `cvrouter.py`, `classify_pdf`, `pdf_text_cached`, `notify`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **What connects `install.sh script` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Index` be split into smaller, more focused modules?**
  _Cohesion score 0.1206896551724138 - nodes in this community are weakly interconnected._