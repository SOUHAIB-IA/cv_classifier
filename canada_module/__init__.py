"""Canada Resume Studio — Canadian-format resumes, independent of the pipeline.

This package READS the CV index and the shared rendering helpers. It never
writes to the index, never touches the pipeline database, and never puts a file
anywhere the watcher looks: the watcher observes `watch_dir` non-recursively
(watcher.py, `recursive=False` and a plain `glob("*.pdf")`), so output under
`canada_module/output/` is out of its reach by construction.

The rules live in `canada_rules.yaml`, not in Python. RESEARCH.md says where
each one comes from and how much to trust it.
"""
__version__ = "0.1.0"
