"""Job sourcing from public ATS job-board endpoints.

Greenhouse, Lever and Ashby all publish a company's open postings as public,
unauthenticated JSON — that is what these endpoints are for. Each adapter turns
one company board into normalised JobRecord dicts.

Deliberately NOT here:
  LinkedIn  robots.txt disallows it. Paste LinkedIn postings in by hand
            (pipeline.source --manual).
  Indeed    no usable public API outside a partner agreement.
  Workday   each tenant is its own undocumented endpoint; add per company if
            one matters enough.

These APIs are per company: there is no "all AI jobs in Casablanca" query.
Coverage is exactly the list of boards in pipeline.toml.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import httpx

import matcher
from .textutil import html_to_text

UA = "cv-router-pipeline/1.0 (personal job search; low volume)"


def _date(v) -> str:
    """ISO date from an ISO string or an epoch in milliseconds."""
    if v is None or v == "":
        return ""
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date().isoformat()
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date().isoformat()
    except (ValueError, OSError, OverflowError):
        return str(v)[:10]


def _record(source, board, sid, company, title, location, jd, apply_url,
            jd_url, posted) -> dict:
    return {
        "id": f"{source}:{sid}",
        "source": source,
        "board": board,
        "company": company,
        "title": (title or "").strip(),
        "location": (location or "").strip(),
        "jd_text": re.sub(r"[ \t\u00a0]+", " ", jd or "").strip(),
        "apply_url": apply_url or jd_url or "",
        "jd_url": jd_url or apply_url or "",
        "language": matcher.guess_language(f"{title}\n{jd}"),
        "posted_date": _date(posted),
    }


def _pretty(board: str) -> str:
    return re.sub(r"[-_]+", " ", board).title()


# ------------------------------------------------------------------ adapters --
def greenhouse(client: httpx.Client, board: str) -> list[dict]:
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                   params={"content": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append(_record(
            "greenhouse", board, j["id"],
            j.get("company_name") or _pretty(board),
            j.get("title"), (j.get("location") or {}).get("name", ""),
            html_to_text(j.get("content", "")),
            j.get("absolute_url"), j.get("absolute_url"),
            j.get("first_published") or j.get("updated_at")))
    return out


def lever(client: httpx.Client, board: str) -> list[dict]:
    r = client.get(f"https://api.lever.co/v0/postings/{board}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        # Lever splits the ad: intro, then titled lists (requirements live
        # there), then a closing section. All of it is the job description.
        parts = [j.get("descriptionPlain") or html_to_text(j.get("description", ""))]
        for lst in j.get("lists") or []:
            parts.append(f"{lst.get('text', '')}\n{html_to_text(lst.get('content', ''))}")
        parts.append(j.get("additionalPlain") or html_to_text(j.get("additional", "")))
        loc = cat.get("location") or ", ".join(cat.get("allLocations") or [])
        if j.get("workplaceType"):
            loc = f"{loc} ({j['workplaceType']})" if loc else j["workplaceType"]
        out.append(_record(
            "lever", board, j["id"], _pretty(board), j.get("text"), loc,
            "\n\n".join(p for p in parts if p).strip(),
            j.get("applyUrl"), j.get("hostedUrl"), j.get("createdAt")))
    return out


def ashby(client: httpx.Client, board: str) -> list[dict]:
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}",
                   params={"includeCompensation": "false"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        loc = j.get("location") or ""
        extra = [x.get("location") for x in j.get("secondaryLocations") or []
                 if isinstance(x, dict) and x.get("location")]
        if extra:
            loc = ", ".join([loc] + extra) if loc else ", ".join(extra)
        if j.get("isRemote") or (j.get("workplaceType") or "").lower() == "remote":
            loc = f"{loc} (remote)" if loc else "remote"
        out.append(_record(
            "ashby", board, j["id"], _pretty(board), j.get("title"), loc,
            j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml", "")),
            j.get("applyUrl"), j.get("jobUrl"), j.get("publishedAt")))
    return out


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "ashby": ashby}


def client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True,
                        headers={"User-Agent": UA, "Accept": "application/json"})


def probe(board: str, timeout: float = 15) -> dict[str, int | str]:
    """Which ATS hosts this company slug, and how many postings it has."""
    res: dict[str, int | str] = {}
    with client(timeout) as c:
        for name, fn in ADAPTERS.items():
            try:
                res[name] = len(fn(c, board))
            except httpx.HTTPStatusError as e:
                res[name] = f"HTTP {e.response.status_code}"
            except Exception as e:
                res[name] = type(e).__name__
    return res
