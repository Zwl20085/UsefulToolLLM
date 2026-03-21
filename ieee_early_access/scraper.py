"""
IEEE Xplore early-access paper scraper.

Given a list of journal page URLs (e.g. https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34),
this module extracts the publication number, queries the IEEE Xplore internal REST API,
and returns the most-recent early-access papers.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
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
_INTER_REQUEST_DELAY = 1.0  # seconds between journal requests (be polite)


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
      https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=6245516
    Also accepts bare numeric strings.
    """
    if url.isdigit():
        return url

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)

    if "punumber" in qs:
        return qs["punumber"][0]

    # fallback: look for any run of digits after 'punumber' anywhere in the raw URL
    m = re.search(r"punumber[=/_](\d+)", url, re.IGNORECASE)
    if m:
        return m.group(1)

    raise ValueError(f"Cannot extract publication number from URL: {url!r}")


def _fetch_journal_name(pub_number: str, session: requests.Session) -> str:
    """Try to resolve the human-readable journal name from the publication page."""
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
    for link in record.get("pdfPath", []) if isinstance(record.get("pdfPath"), list) else []:
        pdf_link = "https://ieeexplore.ieee.org" + link
        break
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


# ── public API ───────────────────────────────────────────────────────────────

def fetch_early_access_papers(
    journal_url: str,
    count: int = 30,
    session: requests.Session | None = None,
) -> JournalResult:
    """Fetch up to *count* early-access papers for a single IEEE journal URL."""
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

    params = {
        "queryText": "*",
        "newsearch": "true",
        "sortType": "paper-pub-date",
        "contentType": "early-access",
        "publicationNumber": pub_number,
        "rowsPerPage": str(count),
        "pageNumber": "1",
    }

    try:
        resp = session.get(
            _IEEE_SEARCH_API,
            params=params,
            headers=_HEADERS,
            timeout=_REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return JournalResult(
            journal_url=journal_url,
            journal_name=journal_name,
            pub_number=pub_number,
            error=f"HTTP error: {exc}",
        )
    except ValueError:
        return JournalResult(
            journal_url=journal_url,
            journal_name=journal_name,
            pub_number=pub_number,
            error="Invalid JSON in API response",
        )

    records = data.get("articles", [])
    papers = [_build_paper(r, journal_name) for r in records]

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
) -> list[JournalResult]:
    """Fetch early-access papers for every URL in *journal_urls* sequentially."""
    results: list[JournalResult] = []
    with requests.Session() as session:
        for i, url in enumerate(journal_urls):
            print(f"  [{i + 1}/{len(journal_urls)}] Fetching: {url}")
            result = fetch_early_access_papers(url, count=count, session=session)
            if result.error:
                print(f"    ⚠  Error: {result.error}")
            else:
                print(f"    ✓  {result.journal_name}: {len(result.papers)} papers")
            results.append(result)

            if i < len(journal_urls) - 1:
                time.sleep(_INTER_REQUEST_DELAY)

    return results
