"""
IEEE Early Access Paper Viewer — Flask web application.

Usage:
    python app.py                        # uses default journals from config.py
    python app.py --journals url1 url2   # override with custom journal URLs
    python app.py --export papers.html   # export static HTML instead of serving

The app fetches early-access papers on startup (or on manual refresh) and
serves them as a live web page.
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from flask import Flask, render_template, redirect, url_for

from scraper import fetch_all_journals, fetch_article_abstract, JournalResult
import config

# ── Flask setup ───────────────────────────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).parent / "templates"
app = Flask(__name__, template_folder=str(TEMPLATE_DIR))

# In-memory cache: refreshed on startup and on /refresh
_cache: dict = {
    "results": [],
    "fetch_time": "never",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _do_fetch(journal_urls: list[str], count: int, days_back: int | None, max_retries: int) -> None:
    """Populate the in-memory cache (runs in a background thread)."""
    print(f"\nFetching {count} early-access papers from {len(journal_urls)} journal(s)…")
    results = fetch_all_journals(journal_urls, count=count, days_back=days_back, max_retries=max_retries)
    _cache["results"] = results
    _cache["fetch_time"] = _now_str()
    total = sum(len(r.papers) for r in results)
    print(f"Done — {total} papers fetched at {_cache['fetch_time']}\n")


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    results: list[JournalResult] = _cache["results"]
    if not results:
        # First visit before background fetch finishes
        return (
            "<html><body style='font-family:sans-serif;padding:2rem'>"
            "<h2>⏳ Fetching papers…</h2>"
            "<p>Please wait a moment and then <a href='/'>refresh</a>.</p>"
            "</body></html>"
        )
    return render_template(
        "index.html",
        results=results,
        fetch_time=_cache["fetch_time"],
    )


@app.route("/refresh")
def refresh():
    """Re-fetch all journals and redirect back to the main page."""
    urls = app.config["JOURNAL_URLS"]
    count = app.config["PAPER_COUNT"]
    days_back = app.config["DAYS_BACK"]
    max_retries = app.config["MAX_RETRIES"]
    # Run in background so the redirect happens immediately
    Thread(target=_do_fetch, args=(urls, count, days_back, max_retries), daemon=True).start()
    return redirect(url_for("index"))


@app.route("/health")
def health():
    return {"status": "ok", "fetch_time": _cache["fetch_time"]}


@app.route("/abstract/<article_number>")
def get_abstract(article_number: str):
    """Proxy: return the full abstract for one IEEE article as JSON.

    Response keys:
        abstract  (str)  — full text, or empty on failure
        source    (str)  — which source provided it
        truncated (bool) — True when every source returned only a snippet
    """
    if not article_number.isdigit():
        return {"abstract": "", "source": "none", "truncated": True}, 400
    result = fetch_article_abstract(article_number)
    app.logger.info(
        "abstract proxy [%s] source=%s truncated=%s len=%d",
        article_number,
        result["source"],
        result["truncated"],
        len(result["abstract"]),
    )
    return result


# ── static export ─────────────────────────────────────────────────────────────

def export_html(
    journal_urls: list[str],
    count: int,
    output_path: str,
    days_back: int | None = None,
    max_retries: int = 3,
) -> None:
    """Fetch papers and write a single self-contained HTML file."""
    print(f"Exporting to {output_path} …")
    results = fetch_all_journals(journal_urls, count=count, days_back=days_back, max_retries=max_retries)
    fetch_time = _now_str()

    with app.app_context():
        html = render_template(
            "index.html",
            results=results,
            fetch_time=fetch_time,
        )

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"Saved: {output_path}")


# ── CLI entry point ───────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="IEEE Early Access Paper Viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app.py
  python app.py --journals https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34
  python app.py --count 20 --port 8080
  python app.py --export output.html
        """,
    )
    parser.add_argument(
        "--journals",
        nargs="+",
        metavar="URL",
        help="One or more IEEE journal page URLs (overrides config.py)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=config.PAPER_COUNT,
        metavar="N",
        help=f"Number of early-access papers to fetch per journal (default: {config.PAPER_COUNT})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 5000)),
        help="Port to listen on (default: 5000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window automatically",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=config.DAYS_BACK,
        metavar="N",
        help="Only show papers published within the last N days (default: no filter)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=config.MAX_RETRIES,
        metavar="N",
        help=f"Retry attempts per request on network errors (default: {config.MAX_RETRIES})",
    )
    parser.add_argument(
        "--export",
        metavar="FILE",
        help="Export a static HTML file instead of starting the server",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    journal_urls = args.journals or config.JOURNAL_URLS

    if not journal_urls:
        print("Error: no journal URLs configured. Edit config.py or pass --journals.")
        sys.exit(1)

    # ── static export mode ────────────────────────────────────────────────────
    if args.export:
        export_html(journal_urls, args.count, args.export, days_back=args.days_back, max_retries=args.max_retries)
        return

    # ── web server mode ───────────────────────────────────────────────────────
    app.config["JOURNAL_URLS"] = journal_urls
    app.config["PAPER_COUNT"] = args.count
    app.config["DAYS_BACK"] = args.days_back
    app.config["MAX_RETRIES"] = args.max_retries

    # Kick off background fetch so the server starts immediately
    Thread(target=_do_fetch, args=(journal_urls, args.count, args.days_back, args.max_retries), daemon=True).start()

    url = f"http://localhost:{args.port}"
    print(f"\n{'='*50}")
    print(f"  IEEE Early Access Viewer")
    print(f"  Serving at: {url}")
    print(f"  Refresh:    {url}/refresh")
    print(f"  Ctrl-C to stop")
    print(f"{'='*50}\n")

    if not args.no_browser:
        # Open browser after a short delay so Flask has time to start
        Thread(
            target=lambda: (
                __import__("time").sleep(1.5),
                webbrowser.open(url),
            ),
            daemon=True,
        ).start()

    app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()
