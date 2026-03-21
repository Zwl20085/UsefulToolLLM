"""
Flask web server: fetches IEEE early-access papers and serves an HTML page.
"""

from __future__ import annotations

import threading
import webbrowser
import logging
from pathlib import Path

from flask import Flask, render_template, request, jsonify

from .scraper import fetch_all_journals

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

# Default journal URLs (can be overridden via the web UI)
DEFAULT_JOURNALS: list[str] = [
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=4387790",
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=4358729",
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=4957013",
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=7098407",
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=4359240",
    "https://ieeexplore.ieee.org/xpl/tocresult.jsp?isnumber=4785241",
]


@app.route("/")
def index():
    return render_template("index.html", default_journals="\n".join(DEFAULT_JOURNALS))


@app.route("/fetch", methods=["POST"])
def fetch():
    """API endpoint: accepts JSON body {urls: [...]}, returns paper data."""
    body = request.get_json(silent=True) or {}
    raw_urls = body.get("urls", DEFAULT_JOURNALS)
    max_papers = int(body.get("max_papers", 30))

    if isinstance(raw_urls, str):
        raw_urls = [u.strip() for u in raw_urls.splitlines() if u.strip()]

    results = fetch_all_journals(raw_urls, max_papers_per_journal=max_papers)

    payload = []
    for r in results:
        payload.append(
            {
                "journal_url": r.journal_url,
                "journal_name": r.journal_name,
                "pub_number": r.pub_number,
                "error": r.error,
                "papers": [
                    {
                        "title": p.title,
                        "abstract": p.abstract,
                        "url": p.url,
                        "authors": p.authors,
                        "doi": p.doi,
                        "publication_date": p.publication_date,
                    }
                    for p in r.papers
                ],
            }
        )

    return jsonify(payload)


def run(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True) -> None:
    """Start the Flask dev server, optionally opening the browser."""
    if open_browser:
        url = f"http://{host}:{port}"
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    app.run(host=host, port=port, debug=False)
