# CLAUDE.md — UsefulToolLLM

Project-level instructions for Claude Code when working in this repository.

## Project Purpose

`UsefulToolLLM` is a growing collection of research productivity tools.
Current tools:
- **IEEE Early Access Paper Viewer** (`ieee_early_access/`) — fetches and displays recent early-access papers from IEEE Xplore.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web framework | Flask 3.x |
| HTTP client | `requests` + `BeautifulSoup4` |
| Frontend | Vanilla HTML/CSS/JS (no build step) |

## Repository Layout

```
UsefulToolLLM/
├── ieee_early_access/      # Tool 1 package
│   ├── scraper.py          # Data-fetching logic (no side effects)
│   ├── server.py           # Flask app + routes
│   └── templates/          # Jinja2 / static HTML
├── main.py                 # CLI entry point
├── requirements.txt
├── README.md
└── CLAUDE.md               # ← you are here
```

New tools should each live in their own top-level package with the same pattern:
`<tool_name>/scraper.py`, `<tool_name>/server.py`, `<tool_name>/templates/`.

## Development Guidelines

### Adding a New Tool

1. Create a new package directory, e.g. `arxiv_digest/`.
2. Implement `scraper.py` (pure data fetching, no Flask imports).
3. Implement `server.py` (Flask Blueprint preferred for composability).
4. Register the Blueprint in a top-level `app.py` (create it when there are 2+ tools).
5. Update `README.md` with setup instructions.

### Coding Standards

- Follow `common/coding-style.md`: immutable data, small functions (<50 lines), small files (<800 lines).
- No hardcoded secrets — use environment variables or a config file outside version control.
- Validate all external data (API responses, user URL input) before processing.
- Handle `requests.RequestException` at every network call; never let unhandled exceptions crash the server.

### Running Locally

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt
python main.py
```

### Testing

- Unit-test `scraper.py` with mocked HTTP responses (`unittest.mock.patch`).
- Target 80%+ coverage per `common/testing.md`.
- Run: `pytest tests/`

### IEEE Xplore Scraper Notes

- The scraper uses the public IEEE Xplore REST endpoint `/rest/search` — no API key needed.
- It extracts the `punumber` from the journal TOC HTML before querying early-access papers.
- Respect the site: default delay between journal requests is **1 second** (`delay_seconds` param).
- Do NOT add authentication headers or attempt to bypass rate limiting.

## Commit Convention

Follow `common/git-workflow.md`:
```
feat: add arxiv digest tool
fix: handle missing punumber gracefully
docs: update README with new journal list
```
