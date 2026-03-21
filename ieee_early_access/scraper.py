"""
IEEE Xplore early-access paper scraper.

Given a list of journal page URLs (e.g. https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34),
this module extracts the publication number, queries the IEEE Xplore internal REST API,
and returns the most-recent early-access papers.

Robustness improvements over v1 (inspired by IEEEXplore-Tracker):
  - Retry with exponential back-off on transient network errors
  - Pagination: fetches multiple pages to reach the requested paper count
  - Optional date filtering (days_back) to restrict results to recent papers
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests

# ── constants ────────────────────────────────────────────────────────────────

_IEEE_SEARCH_API = "https://ieeexplore.ieee.org/rest/search"
_IEEE_ABSTRACT_BASE = "https://ieeexplore.ieee.org/document/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://ieeexplore.ieee.org/",
    "Accept": "application/json, text/plain, */*",
}

_REQUEST_TIMEOUT = 20   # seconds
_INTER_REQUEST_DELAY = 1.0  # seconds between requests (be polite)
_PAGE_SIZE = 25  # records per page request
_RETRY_BACKOFF = 2.0  # seconds; doubles each attempt

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


def _get_with_retry(
    session: requests.Session,
    url: str,
    params: dict,
    max_retries: int,
) -> requests.Response:
    """GET with exponential back-off retries on transient errors."""
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
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
        resp = session.get(url, headers=_HEADERS, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return data.get("publicationTitle", f"Journal {pub_number}")
    except Exception:
        return f"Journal {pub_number}"


def _build_paper(record: dict, journal_name: str) -> Paper:
    """Convert one API record dict into a Paper dataclass."""
    article_number = str(record.get("articleNumber", ""))
    doi = record.get("doi", "")

    authors_raw = record.get("authors", [])
    if isinstance(authors_raw, list):
        authors = [a.get("preferredName") or a.get("normalizedName", "") for a in authors_raw]
    else:
        authors = []

    pdf_link = ""
    pdf_path = record.get("pdfPath", [])
    if isinstance(pdf_path, list) and pdf_path:
        pdf_link = "https://ieeexplore.ieee.org" + pdf_path[0]
    if not pdf_link and article_number:
        pdf_link = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber={article_number}"

    return Paper(
        title=record.get("title", "(no title)"),
        abstract=record.get("abstract", ""),
        authors=authors,
        doi=doi,
        article_number=article_number,
        publication_date=record.get("onlineDateOfPublication") or record.get("publicationDate", ""),
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
        params = {
            "queryText": "*",
            "newsearch": "true",
            "sortType": "paper-pub-date",
            "contentType": "early-access",
            "publicationNumber": pub_number,
            "rowsPerPage": str(_PAGE_SIZE),
            "pageNumber": str(page),
        }

        try:
            resp = _get_with_retry(session, _IEEE_SEARCH_API, params, max_retries)
            data = resp.json()
        except requests.RequestException as exc:
            if own_session:
                session.close()
            return JournalResult(
                journal_url=journal_url,
                journal_name=journal_name,
                pub_number=pub_number,
                papers=[_build_paper(r, journal_name) for r in all_records],
                error=f"HTTP error on page {page}: {exc}",
            )
        except ValueError:
            if own_session:
                session.close()
            return JournalResult(
                journal_url=journal_url,
                journal_name=journal_name,
                pub_number=pub_number,
                papers=[_build_paper(r, journal_name) for r in all_records],
                error=f"Invalid JSON in API response on page {page}",
            )

        page_records = data.get("articles", [])
        all_records.extend(page_records)

        if total_available is None:
            total_available = int(data.get("totalRecords", 0))

        # Stop when we have enough or there are no more pages
        enough = len(all_records) >= count
        no_more = not page_records or len(all_records) >= total_available
        if enough or no_more:
            break

        page += 1
        time.sleep(_INTER_REQUEST_DELAY)

    papers = [_build_paper(r, journal_name) for r in all_records[:count]]
    papers = _filter_by_date(papers, days_back)

    if own_session:
        session.close()

    return JournalResult(
        journal_url=journal_url,
        journal_name=journal_name,
        pub_number=pub_number,
        papers=papers,
    )


def fetch_all_journals(
    journal_urls: list[str],
    count: int = 30,
    days_back: int | None = None,
    max_retries: int = 3,
) -> list[JournalResult]:
    """Fetch early-access papers for every URL in *journal_urls* sequentially."""
    results: list[JournalResult] = []
    with requests.Session() as session:
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
