# UsefulToolLLM

A collection of research productivity tools.

## Tools

### `ieee_early_access/` — IEEE Early Access Paper Viewer

Fetch and browse the latest **early-access papers** from any IEEE Transactions journal in a clean, searchable web page.

![Screenshot placeholder](docs/screenshot.png)

#### Features
- Configurable list of IEEE journal URLs
- Fetches up to 30 (configurable) early-access papers per journal
- Displays: title, authors, publication date, abstract, links to abstract page + PDF
- In-page search/filter by keyword or journal
- Static HTML export (no server needed to share results)
- Opens your browser automatically on startup

#### Quick Start

```bash
cd ieee_early_access

# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Edit the journal list
#    Open config.py and update JOURNAL_URLS

# 3. Run
python app.py
# → Opens http://localhost:5000 in your browser automatically
```

#### Configure Your Journals

Open `ieee_early_access/config.py`:

```python
JOURNAL_URLS: list[str] = [
    # IEEE Transactions on Pattern Analysis and Machine Intelligence
    "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34",

    # Add any IEEE journal page URL here …
]

PAPER_COUNT: int = 30   # papers per journal
```

**Finding a journal URL:**
1. Visit https://ieeexplore.ieee.org/browse/periodicals/title
2. Search for your journal and click it
3. Copy the URL from your browser (it contains `punumber=…`)

#### CLI Options

```
python app.py [OPTIONS]

Options:
  --journals URL [URL ...]   Override config.py journal URLs
  --count N                  Papers per journal (default: 30)
  --port PORT                Server port (default: 5000)
  --no-browser               Don't open browser automatically
  --export FILE              Write static HTML file instead of serving
```

#### Examples

```bash
# Fetch 50 papers from TPAMI
python app.py --journals "https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34" --count 50

# Export to a shareable HTML file
python app.py --export papers_$(date +%Y%m%d).html

# Run on a custom port
python app.py --port 8080
```

#### Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | Web server + HTML rendering |
| `requests` | HTTP client for IEEE Xplore API |
| `jinja2` | HTML templating (bundled with Flask) |

> **Note**: This tool uses IEEE Xplore's internal REST API (the same one their website uses). No API key is required, but behavior may change if IEEE updates their frontend. Use responsibly and in accordance with IEEE's terms of service.

---

## Roadmap

- [ ] arXiv paper fetcher
- [ ] Google Scholar citation alert aggregator
- [ ] Semantic Scholar related-work explorer

## Contributing

PRs welcome. Please open an issue first for large changes.

## License

MIT
