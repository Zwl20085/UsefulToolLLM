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
# Default list covers a selection of flagship IEEE Transactions journals.
# Modify freely.

JOURNAL_URLS: list[str] = [
    # IEEE Transactions on Pattern Analysis and Machine Intelligence (TPAMI)
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34",

    # IEEE Transactions on Neural Networks and Learning Systems (TNNLS)
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=5962385",

    # IEEE Transactions on Image Processing (TIP)
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=83",

    # IEEE Transactions on Cybernetics
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=6221036",

    # IEEE Transactions on Knowledge and Data Engineering (TKDE)
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=69",
]

# Number of early-access papers to retrieve per journal (max recommended: 100)
PAPER_COUNT: int = 30
