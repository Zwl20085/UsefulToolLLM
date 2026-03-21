"""
IEEE Xplore Early Access paper scraper.

Uses the IEEE Xplore REST API to fetch the most recent early-access papers
for a list of journal URLs.  Each URL should be a table-of-contents page:
    https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=XXXXXXX
The scraper extracts the publication number (punumber) from the page, then
queries the early-access endpoint.
"""

from __future__ import annotations

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://ieeexplore.ieee.org/",
}

SEARCH_API = "https://ieeexplore.ieee.org/rest/search"
PAPER_BASE = "https://ieeexplore.ieee.org/document/"


@dataclass
class Paper:
    title: str
    abstract: str
    url: str
    authors: list[str] = field(default_factory=list)
    doi: str = ""
    publication_date: str = ""


def _get_publication_number(journal_url: str, session: requests.Session) -> Optional[str]:
    """Fetch the journal TOC page and extract the punumber."""
    try:
        resp = session.get(journal_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("Failed to fetch journal page %s: %s", journal_url, exc)
        return None

    # 1) Try canonical meta tag: <meta name="citation_journal_title" ...>
    soup = BeautifulSoup(resp.text, "html.parser")

    # 2) Try to find punumber in the page HTML / JS blobs
    patterns = [
        r'"punumber"\s*:\s*"?(\d+)"?',
        r'punumber=(\d+)',
        r'"publicationNumber"\s*:\s*"?(\d+)"?',
    ]
    for pat in patterns:
        m = re.search(pat, resp.text)
        if m:
            return m.group(1)

    # 3) Fallback: check canonical link or og:url
    for tag in soup.find_all("link", rel="canonical"):
        m = re.search(r'punumber[=/](\d+)', tag.get("href", ""))
        if m:
            return m.group(1)

    logger.warning("Could not extract punumber from %s", journal_url)
    return None


def _get_journal_name(journal_url: str, session: requests.Session) -> str:
    """Return the journal title from the TOC page, best-effort."""
    try:
        resp = session.get(journal_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        # Try <title> tag
        title_tag = soup.find("title")
        if title_tag:
            raw = title_tag.get_text(" ", strip=True)
            # Strip common suffixes
            raw = re.sub(r"\s*[-|].*IEEE Xplore.*", "", raw, flags=re.I)
            return raw.strip()
    except Exception:
        pass
    return journal_url


def fetch_early_access_papers(
    pub_number: str,
    session: requests.Session,
    max_papers: int = 30,
) -> list[Paper]:
    """Query the IEEE Xplore REST API for early-access papers."""
    params = {
        "queryText": "*",
        "newsearch": "true",
        "publicationNumber": pub_number,
        "earlyAccess": "True",
        "sortType": "newest",
        "pageNumber": "1",
        "rowsPerPage": str(max_papers),
    }
    try:
        resp = session.get(SEARCH_API, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("API request failed for pub %s: %s", pub_number, exc)
        return []
    except ValueError as exc:
        logger.error("JSON parse error for pub %s: %s", pub_number, exc)
        return []

    papers: list[Paper] = []
    for item in data.get("articles", []):
        article_number = str(item.get("articleNumber", ""))
        title = item.get("title", "Untitled").strip()
        abstract = item.get("abstract", "No abstract available.").strip()
        doi = item.get("doi", "")
        pub_date = item.get("publicationDate", item.get("onlinedatestart", ""))
        authors_raw = item.get("authors", {})
        if isinstance(authors_raw, dict):
            author_list = [a.get("normalizedName", "") for a in authors_raw.get("authors", [])]
        elif isinstance(authors_raw, list):
            author_list = [a.get("normalizedName", str(a)) for a in authors_raw]
        else:
            author_list = []

        papers.append(
            Paper(
                title=title,
                abstract=abstract,
                url=PAPER_BASE + article_number if article_number else "",
                authors=author_list,
                doi=doi,
                publication_date=pub_date,
            )
        )

    return papers


@dataclass
class JournalResult:
    journal_url: str
    journal_name: str
    pub_number: str
    papers: list[Paper]
    error: str = ""


def fetch_all_journals(
    journal_urls: list[str],
    max_papers_per_journal: int = 30,
    delay_seconds: float = 1.0,
) -> list[JournalResult]:
    """Fetch early-access papers for every journal URL."""
    results: list[JournalResult] = []
    session = requests.Session()

    for url in journal_urls:
        url = url.strip()
        if not url:
            continue

        logger.info("Processing journal: %s", url)
        journal_name = _get_journal_name(url, session)
        pub_number = _get_publication_number(url, session)

        if not pub_number:
            results.append(
                JournalResult(
                    journal_url=url,
                    journal_name=journal_name,
                    pub_number="",
                    papers=[],
                    error="Could not determine publication number from URL.",
                )
            )
            continue

        papers = fetch_early_access_papers(pub_number, session, max_papers_per_journal)
        results.append(
            JournalResult(
                journal_url=url,
                journal_name=journal_name,
                pub_number=pub_number,
                papers=papers,
            )
        )
        time.sleep(delay_seconds)

    return results
