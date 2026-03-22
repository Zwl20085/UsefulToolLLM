"""
IEEE Xplore early-access paper scraper.

Given a list of journal page URLs (e.g. https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34),
this module extracts the publication number, queries the IEEE Xplore internal REST API,
and returns the most-recent early-access papers.

API notes (as of 2025):
  - The /rest/search endpoint requires POST with a JSON body (GET → 405).
  - publicationNumber must be sent as integer field "punumber".
  - queryText:"*" and contentType:"early-access" both cause HTTP 500;
    instead we fetch all journal papers and filter client-side via isEarlyAccess.
  - Session cookies (AWSALBAPP, WLSESSION) must be initialised by a prior
    GET to the homepage before the search POST will succeed.

Robustness features:
  - Session cookie initialisation before first search request.
  - Retry with exponential back-off on transient network errors.
  - Pagination: fetches multiple pages to reach the requested paper count.
  - Optional date filtering (days_back) to restrict results to recent papers.
"""

from __future__ import annotations

import html as _html
import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests

# ── constants ────────────────────────────────────────────────────────────────

_IEEE_HOME = "https://ieeexplore.ieee.org/"
_IEEE_SEARCH_API = "https://ieeexplore.ieee.org/rest/search"
_IEEE_ABSTRACT_BASE = "https://ieeexplore.ieee.org/document/"

_HEADERS_GET = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_HEADERS_POST = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ieeexplore.ieee.org/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://ieeexplore.ieee.org",
}

_REQUEST_TIMEOUT = 20   # seconds
_INTER_REQUEST_DELAY = 1.0  # seconds between requests (be polite)
_PAGE_SIZE = 25  # records per page request
_RETRY_BACKOFF = 2.0  # seconds; doubles each attempt

# Abstracts shorter than this are treated as API snippets; trigger HTML fallback.
_MIN_ABSTRACT_LEN = 600  # characters

# Date formats returned by the IEEE Xplore API
_DATE_FORMATS = [
    "%d %B %Y",   # "01 March 2024"
    "%Y-%m-%d",   # "2024-03-01"
    "%B %Y",      # "March 2024"
    "%Y",         # "2024"
]


# ── data model ───────────────────────────────────────────────────────────────

@dataclass
class Paper:
    title: str
    abstract: str
    authors: list[str]
    doi: str
    article_number: str
    publication_date: str
    journal_name: str
    url: str
    pdf_url: str = ""

    @property
    def short_abstract(self) -> str:
        """Return first 400 characters of abstract for preview."""
        if len(self.abstract) <= 400:
            return self.abstract
        return self.abstract[:400].rsplit(" ", 1)[0] + " …"


@dataclass
class JournalResult:
    journal_url: str
    journal_name: str
    pub_number: str
    papers: list[Paper] = field(default_factory=list)
    error: str = ""


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_pub_number(url: str) -> str:
    """Extract publication number from an IEEE journal URL.

    Supports forms like:
      https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34
      https://ieeexplore.ieee.org/xpl/mostRecentIssue.jsp?punumber=8234
      https://ieeexplore.ieee.org/browse/journals/34
      https://ieeexplore.ieee.org/xpl/conhome/34/proceeding
    Also accepts bare numeric strings.
    """
    if url.isdigit():
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "punumber" in qs:
        return qs["punumber"][0]

    m = re.search(r"punumber[=/_](\d+)", url, re.IGNORECASE)
    if m:
        return m.group(1)

    m = re.search(r"/(?:browse/journals|xpl/conhome)/(\d+)", parsed.path, re.IGNORECASE)
    if m:
        return m.group(1)

    raise ValueError(f"Cannot extract publication number from URL: {url!r}")


def _parse_date(date_str: str) -> datetime | None:
    """Parse an IEEE date string into a datetime, trying multiple formats."""
    if not date_str:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _init_session(session: requests.Session) -> None:
    """GET the IEEE homepage to acquire required session cookies."""
    try:
        session.get(_IEEE_HOME, headers=_HEADERS_GET, timeout=_REQUEST_TIMEOUT)
    except requests.RequestException:
        pass  # proceed anyway; request may still work


def _post_with_retry(
    session: requests.Session,
    url: str,
    payload: dict,
    max_retries: int,
) -> requests.Response:
    """POST JSON with exponential back-off retries on transient errors."""
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_retries):
        try:
            resp = session.post(url, json=payload, headers=_HEADERS_POST, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait = _RETRY_BACKOFF * (2 ** attempt)
                time.sleep(wait)
    raise last_exc


def _fetch_journal_name(pub_number: str, session: requests.Session) -> str:
    """Resolve the human-readable journal name from the publication metadata endpoint."""
    try:
        url = f"https://ieeexplore.ieee.org/rest/publication/home/metadata?pubid={pub_number}"
        resp = session.get(url, headers=_HEADERS_POST, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("displayTitle") or data.get("publicationTitle") or f"Journal {pub_number}"
    except Exception:
        return f"Journal {pub_number}"


def _build_paper(record: dict, journal_name: str) -> Paper:
    """Convert one API record dict into a Paper dataclass."""
    article_number = str(record.get("articleNumber", ""))
    doi = record.get("doi", "")

    authors_raw = record.get("authors", [])
    if isinstance(authors_raw, list):
        authors = [
            a.get("preferredName") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
            for a in authors_raw
        ]
    else:
        authors = []

    # pdfLink is a relative path like "/stamp/stamp.jsp?tp=&arnumber=XXXXX"
    pdf_link = record.get("pdfLink", "")
    if pdf_link and not pdf_link.startswith("http"):
        pdf_link = "https://ieeexplore.ieee.org" + pdf_link
    if not pdf_link and article_number:
        pdf_link = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={article_number}"

    # publicationDate is null for early-access; fall back to publicationYear
    pub_date = record.get("publicationDate") or record.get("publicationYear", "")

    return Paper(
        title=record.get("articleTitle", "(no title)"),
        abstract=record.get("abstract", ""),
        authors=authors,
        doi=doi,
        article_number=article_number,
        publication_date=str(pub_date) if pub_date else "",
        journal_name=record.get("publicationTitle") or journal_name,
        url=(
            _IEEE_ABSTRACT_BASE + article_number
            if article_number
            else f"https://doi.org/{doi}" if doi else ""
        ),
        pdf_url=pdf_link,
    )


def _filter_by_date(papers: list[Paper], days_back: int | None) -> list[Paper]:
    """Drop papers older than *days_back* days. Papers with unparseable dates are kept."""
    if days_back is None:
        return papers
    cutoff = datetime.now() - timedelta(days=days_back)
    result = []
    for p in papers:
        dt = _parse_date(p.publication_date)
        if dt is None or dt >= cutoff:
            result.append(p)
    return result


# ── public API ───────────────────────────────────────────────────────────────

def fetch_early_access_papers(
    journal_url: str,
    count: int = 30,
    days_back: int | None = None,
    max_retries: int = 3,
    session: requests.Session | None = None,
) -> JournalResult:
    """Fetch up to *count* early-access papers for a single IEEE journal URL.

    Args:
        journal_url: IEEE Xplore journal page URL or bare publication number.
        count:       Maximum number of papers to return.
        days_back:   If set, discard papers published more than this many days ago.
        max_retries: Retry attempts per page request on transient errors.
        session:     Optional shared requests.Session for connection reuse.
    """
    own_session = session is None
    if own_session:
        session = requests.Session()
        _init_session(session)

    try:
        pub_number = _extract_pub_number(journal_url)
    except ValueError as exc:
        return JournalResult(
            journal_url=journal_url,
            journal_name="Unknown",
            pub_number="",
            error=str(exc),
        )

    journal_name = _fetch_journal_name(pub_number, session)

    all_records: list[dict] = []
    page = 1
    total_available = None  # learned after first page response

    while True:
        # NOTE: queryText:"*" and contentType:"early-access" both cause HTTP 500.
        # We fetch all journal papers and filter by isEarlyAccess client-side.
        payload = {
            "newsearch": True,
            "highlight": True,
            "returnFacets": ["ALL"],
            "returnType": "SEARCH",
            "matchPubs": True,
            "punumber": int(pub_number),
            "rowsPerPage": _PAGE_SIZE,
            "pageNumber": page,
            "sortType": "newest",
        }

        try:
            resp = _post_with_retry(session, _IEEE_SEARCH_API, payload, max_retries)
            data = resp.json()
        except requests.RequestException as exc:
            if own_session:
                session.close()
            return JournalResult(
                journal_url=journal_url,
                journal_name=journal_name,
                pub_number=pub_number,
                papers=[_build_paper(r, journal_name) for r in all_records
                        if r.get("isEarlyAccess")],
                error=f"HTTP error on page {page}: {exc}",
            )
        except ValueError:
            if own_session:
                session.close()
            return JournalResult(
                journal_url=journal_url,
                journal_name=journal_name,
                pub_number=pub_number,
                papers=[_build_paper(r, journal_name) for r in all_records
                        if r.get("isEarlyAccess")],
                error=f"Invalid JSON in API response on page {page}",
            )

        page_records = data.get("records", [])
        all_records.extend(page_records)

        if total_available is None:
            total_available = int(data.get("totalRecords", 0))

        # Count only early-access records toward our target
        ea_so_far = sum(1 for r in all_records if r.get("isEarlyAccess"))
        enough = ea_so_far >= count
        no_more = not page_records or len(all_records) >= total_available
        if enough or no_more:
            break

        page += 1
        time.sleep(_INTER_REQUEST_DELAY)

    ea_records = [r for r in all_records if r.get("isEarlyAccess")]
    papers = [_build_paper(r, journal_name) for r in ea_records[:count]]
    papers = _filter_by_date(papers, days_back)

    if own_session:
        session.close()

    return JournalResult(
        journal_url=journal_url,
        journal_name=journal_name,
        pub_number=pub_number,
        papers=papers,
    )


# ── abstract fetch helpers ────────────────────────────────────────────────────

def _parse_json_object(text: str, start: int) -> dict | None:
    """Extract the JSON object starting at text[start] using brace counting.

    Plain regex can't handle arbitrarily nested braces, so we count manually.
    Scans at most 600 000 characters to avoid runaway loops on malformed pages.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    in_string = False
    skip_next = False
    limit = min(start + 600_000, len(text))
    for i in range(start, limit):
        ch = text[i]
        if skip_next:
            skip_next = False
            continue
        if ch == "\\" and in_string:
            skip_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (ValueError, json.JSONDecodeError):
                    return None
    return None


def _try_api_abstract(article_number: str, session: requests.Session) -> str:
    """Try IEEE JSON endpoints for the abstract, returning the longest result.

    Tries the full document endpoint first; if the result is already long
    enough we skip the sub-resource to save a round-trip.
    """
    best = ""
    urls = [
        f"https://ieeexplore.ieee.org/rest/document/{article_number}",
        f"https://ieeexplore.ieee.org/rest/document/{article_number}/abstract",
    ]
    for url in urls:
        try:
            resp = session.get(url, headers=_HEADERS_POST, timeout=_REQUEST_TIMEOUT)
            if not resp.ok:
                continue
            data = resp.json()
            candidate = str(data.get("abstract") or data.get("abstractText") or "")
            if len(candidate) > len(best):
                best = candidate
            if len(best) >= _MIN_ABSTRACT_LEN:
                break  # good enough — skip remaining endpoints
        except Exception:
            continue
    return _html.unescape(best) if best else ""


def _try_html_abstract(article_number: str, session: requests.Session) -> str:
    """Scrape the paper HTML page and extract the abstract from embedded metadata.

    IEEE Xplore is a JavaScript SPA but embeds full article metadata in the
    initial HTML for SEO. We probe three locations in priority order:
      1. xplGlobal JS variable  — legacy and current IEEE Xplore deployments
      2. __NEXT_DATA__ JSON      — Next.js style, used in newer deployments
      3. JSON-LD structured data — schema.org ScholarlyArticle block

    A 403 or timeout is caught and returns an empty string so the caller can
    fall back gracefully without surfacing errors to the user.
    """
    url = f"https://ieeexplore.ieee.org/document/{article_number}"
    try:
        resp = session.get(url, headers=_HEADERS_GET, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        page = resp.text
    except Exception:
        return ""

    # Strategy 1: xplGlobal = {...}
    m = re.search(r"xplGlobal\s*=\s*\{", page)
    if m:
        data = _parse_json_object(page, m.end() - 1)
        if data:
            abstract = (
                data.get("document", {}).get("metadata", {}).get("abstract")
                or data.get("document", {}).get("abstract")
                or data.get("metadata", {}).get("abstract")
            )
            if abstract:
                return _html.unescape(str(abstract))

    # Strategy 2: __NEXT_DATA__
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>\s*\{',
        page,
        re.IGNORECASE,
    )
    if m:
        data = _parse_json_object(page, m.end() - 1)
        if data:
            try:
                pp = data.get("props", {}).get("pageProps", {})
                abstract = (
                    pp.get("article", {}).get("abstract")
                    or pp.get("abstract")
                )
                if abstract:
                    return _html.unescape(str(abstract))
            except (AttributeError, KeyError):
                pass

    # Strategy 3: JSON-LD
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>\s*(\{|\[)',
        page,
        re.IGNORECASE,
    ):
        data = _parse_json_object(page, m.end() - 1)
        if not data:
            continue
        if isinstance(data, list):
            data = next((d for d in data if isinstance(d, dict)), {})
        abstract = data.get("description") or data.get("abstract")
        if abstract:
            return _html.unescape(str(abstract))

    return ""


def fetch_article_abstract(
    article_number: str,
    session: requests.Session | None = None,
) -> dict:
    """Fetch the full abstract for one article using a waterfall of sources.

    Sources tried in order (stops at the first result >= _MIN_ABSTRACT_LEN):
      1. IEEE JSON API  (/rest/document/{id} and /rest/document/{id}/abstract)
      2. HTML scraping  (xplGlobal → __NEXT_DATA__ → JSON-LD)
      3. Best-effort    (returns whatever was found, marked truncated=True)

    Returns a dict:
        abstract  (str)  — the abstract text (empty string on total failure)
        source    (str)  — "api" | "html" | "fallback" | "none"
        truncated (bool) — True when every source returned a short snippet
    """
    own_session = session is None
    if own_session:
        session = requests.Session()
        _init_session(session)
    try:
        # Source 1: JSON API
        api_text = _try_api_abstract(article_number, session)
        if api_text and len(api_text) >= _MIN_ABSTRACT_LEN:
            return {"abstract": api_text, "source": "api", "truncated": False}

        # Source 2: HTML page scraping (small courtesy delay)
        time.sleep(0.5)
        html_text = _try_html_abstract(article_number, session)
        if html_text and len(html_text) >= _MIN_ABSTRACT_LEN:
            return {"abstract": html_text, "source": "html", "truncated": False}

        # Best available (may still be a snippet)
        best = api_text if len(api_text) >= len(html_text) else html_text
        return {
            "abstract": best,
            "source": "fallback" if best else "none",
            "truncated": True,
        }
    except Exception:
        return {"abstract": "", "source": "none", "truncated": True}
    finally:
        if own_session:
            session.close()


def fetch_all_journals(
    journal_urls: list[str],
    count: int = 30,
    days_back: int | None = None,
    max_retries: int = 3,
) -> list[JournalResult]:
    """Fetch early-access papers for every URL in *journal_urls* sequentially."""
    results: list[JournalResult] = []
    with requests.Session() as session:
        _init_session(session)
        for i, url in enumerate(journal_urls):
            print(f"  [{i + 1}/{len(journal_urls)}] Fetching: {url}")
            result = fetch_early_access_papers(
                url,
                count=count,
                days_back=days_back,
                max_retries=max_retries,
                session=session,
            )
            if result.error:
                print(f"    ⚠  Error: {result.error}")
            else:
                print(f"    ✓  {result.journal_name}: {len(result.papers)} papers")
            results.append(result)

            if i < len(journal_urls) - 1:
                time.sleep(_INTER_REQUEST_DELAY)

    return results
