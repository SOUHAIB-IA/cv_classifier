#!/usr/bin/env python3
"""Prove the index survives concurrent writers.

The bug this guards against: two processes each did load() / mutate / save(),
so whoever saved last silently dropped the other's entries. commit() re-reads
inside an flock and merges, so nothing is lost.

Run:  ./.venv/bin/python test_index_concurrency.py
"""
import multiprocessing as mp
import shutil
import sys
import tempfile
from pathlib import Path

import cvrouter as cr

ok = True


def check(label, cond, detail=""):
    global ok
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"  {detail}" if detail else ""))
    ok = ok and cond


def _writer(args):
    """One process writing N records, each as its own commit."""
    cfg_root, who, n = args
    cfg = cr.load_config()
    cfg.cv_root = Path(cfg_root) / "CVs"
    cfg.index_file = Path(cfg_root) / "index.json"
    idx = cr.Index(cfg)
    for i in range(n):
        rel = f"{who}/cv-{i}.pdf"
        (cfg.cv_root / who).mkdir(parents=True, exist_ok=True)
        (cfg.cv_root / rel).write_bytes(b"%PDF-1.4 stub")
        idx.commit(upserts={rel: cr.CVRecord(path=rel, sig=f"{who}-{i}",
                                             summary="x")})
    return who


def _naive_writer(args):
    """The OLD pattern, for contrast: load / mutate / write, no lock."""
    cfg_root, who, n = args
    cfg = cr.load_config()
    cfg.cv_root = Path(cfg_root) / "CVs"
    cfg.index_file = Path(cfg_root) / "index.json"
    idx = cr.Index(cfg)
    for i in range(n):
        rel = f"{who}/cv-{i}.pdf"
        (cfg.cv_root / who).mkdir(parents=True, exist_ok=True)
        (cfg.cv_root / rel).write_bytes(b"%PDF-1.4 stub")
        idx.load()                      # read whole file
        idx.records[rel] = cr.CVRecord(path=rel, sig=f"{who}-{i}", summary="x")
        idx._write_disk(idx.records)    # blind overwrite
    return who


def run(worker, label, procs=4, per=25):
    tmp = Path(tempfile.mkdtemp(prefix="cvidx-"))
    (tmp / "CVs").mkdir()
    cfg = cr.load_config()
    cfg.cv_root, cfg.index_file = tmp / "CVs", tmp / "index.json"
    with mp.Pool(procs) as pool:
        pool.map(worker, [(str(tmp), f"w{k}", per) for k in range(procs)])
    final = cr.Index(cfg)
    got, want = len(final.records), procs * per
    print(f"\n{label}: {got}/{want} entrées conservées")
    shutil.rmtree(tmp)
    return got, want


def main():
    print("1. le motif NAÏF (load / mutate / write) perd des écritures")
    got, want = run(_naive_writer, "   sans verrou")
    check("des entrées sont bien perdues (c'était le bug)", got < want,
          f"{want - got} perdues")

    print("\n2. commit() sous flock ne perd rien")
    got, want = run(_writer, "   avec commit()")
    check("toutes les entrées survivent", got == want)

    print("\n3. prune ne supprime pas ce qu'un autre processus vient d'ajouter")
    tmp = Path(tempfile.mkdtemp(prefix="cvidx-"))
    (tmp / "CVs").mkdir()
    cfg = cr.load_config()
    cfg.cv_root, cfg.index_file = tmp / "CVs", tmp / "index.json"

    a = cr.Index(cfg)                      # l'indexeur démarre, snapshot vide
    (cfg.cv_root / "neuf.pdf").write_bytes(b"%PDF-1.4")
    b = cr.Index(cfg)                      # le watcher range un CV entre-temps
    b.commit(upserts={"neuf.pdf": cr.CVRecord(path="neuf.pdf", sig="n")})

    (cfg.cv_root / "vieux.pdf").write_bytes(b"%PDF-1.4")
    a.commit(upserts={"vieux.pdf": cr.CVRecord(path="vieux.pdf", sig="v")},
             prune=True)                   # l'indexeur termine et élague
    final = set(cr.Index(cfg).records)
    check("le CV ajouté par l'autre processus survit", "neuf.pdf" in final)
    check("le CV de l'indexeur est là", "vieux.pdf" in final)

    print("\n4. prune supprime bien une entrée dont le PDF a disparu")
    (cfg.cv_root / "neuf.pdf").unlink()
    a.commit(prune=True)
    check("entrée orpheline supprimée", "neuf.pdf" not in cr.Index(cfg).records)
    shutil.rmtree(tmp)

    print("\n5. un verrou bloqué lève une erreur claire au lieu de figer")
    tmp = Path(tempfile.mkdtemp(prefix="cvidx-"))
    cfg.index_file = tmp / "index.json"
    i1, i2 = cr.Index(cfg), cr.Index(cfg)
    with i1._flock():
        try:
            i2.commit(upserts={}, timeout=0.3)
            check("timeout levé", False, "aucune exception")
        except cr.IndexLockTimeout:
            check("timeout levé proprement", True)
    shutil.rmtree(tmp)

    print("\n" + ("ALL PASS" if ok else "FAILURES ABOVE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
