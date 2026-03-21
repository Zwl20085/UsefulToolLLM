"""
Configuration for IEEE Early Access Paper Viewer.

Edit JOURNAL_URLS to add or remove journals you want to track.
Each entry should be the IEEE Xplore "Recent Issue" page URL for that journal.

Finding a journal URL:
  1. Go to https://ieeexplore.ieee.org/browse/periodicals/title
  2. Search for your journal
  3. Click the journal → copy the URL from the browser address bar
     e.g. https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34

You can also provide just the publication number (e.g. "34").
"""

# ── Journal URLs to monitor ───────────────────────────────────────────────────
# Power electronics & electric drives journals.

JOURNAL_URLS: list[str] = [
    # IEEE Transactions on Industrial Electronics (TIE) — punumber=41
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=41",

    # IEEE Transactions on Energy Conversion (TEC) — punumber=60
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=60",

    # IEEE Transactions on Industry Applications (TIA) — punumber=28
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=28",

    # IEEE Transactions on Transportation Electrification (TTE) — punumber=6687316
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=6687316",

    # IEEE/ASME Transactions on Mechatronics (TMECH) — punumber=3516
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=3516",

    # IEEE Transactions on Power Electronics (TPEL) — punumber=63
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=63",
]

# Number of early-access papers to retrieve per journal (max recommended: 100)
PAPER_COUNT: int = 30

# Only show papers published within this many days (None = no date filter)
DAYS_BACK: int | None = None

# Retry attempts on transient network errors (per request)
MAX_RETRIES: int = 3
