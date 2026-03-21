# CLAUDE.md — ieee_early_access

## Project Purpose
A Python/Flask tool that fetches the latest early-access papers from configurable IEEE Transactions journals and displays them in a searchable browser page.

## Architecture

```
ieee_early_access/
├── app.py            # Flask server + CLI entry point
├── scraper.py        # IEEE Xplore REST API client
├── config.py         # User-editable journal URL list + settings
├── requirements.txt
└── templates/
    └── index.html    # Jinja2 template (CSS + JS included inline)
```

### Data flow
1. `app.py` reads `config.JOURNAL_URLS` (or `--journals` CLI args).
2. `scraper.fetch_all_journals()` calls the IEEE Xplore internal REST endpoint
   (`/rest/search?contentType=early-access&publicationNumber=…`) for each journal.
3. Results are stored in an in-memory `_cache` dict.
4. The Flask `/` route renders `index.html` with the cached data.

## Key Design Decisions

- **No API key required**: The scraper hits the same undocumented REST endpoint that the IEEE Xplore browser app uses. This may break if IEEE changes their frontend.
- **No database**: All data is in-memory. Restart or `/refresh` re-fetches everything.
- **Static export**: `--export output.html` writes a single portable HTML file with no server dependency.
- **Polite scraping**: 1-second delay between journal requests to avoid rate-limiting.

## How to Add a New Journal
Edit `config.py` → add the IEEE Xplore "Recent Issue" URL to `JOURNAL_URLS`.

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the viewer (opens browser automatically)
python app.py

# Custom journals
python app.py --journals "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34"

# Export static HTML
python app.py --export papers.html

# Change paper count
python app.py --count 50
```

## Testing
There are currently no automated tests. When adding tests:
- Mock `requests.Session.get` to avoid real HTTP calls.
- Test `_extract_pub_number()` with various URL shapes.
- Test `_build_paper()` with real API response fixtures.

## Limitations
- Relies on IEEE Xplore's undocumented internal REST API — may break without notice.
- Abstract truncation is purely cosmetic (first 400 chars); full abstract is always fetched.
- No caching to disk; data is lost on restart.
