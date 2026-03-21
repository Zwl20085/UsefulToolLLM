# UsefulToolLLM

A collection of research productivity tools.

---

## Tool 1 — IEEE Early Access Paper Viewer

Fetches the **30 most recent early-access papers** from a configurable list of IEEE Xplore journals and displays them in a clean, searchable web page.

### Features

- Pulls live data from the IEEE Xplore REST API (no API key required)
- Shows title, authors, publication date, DOI, and abstract for every paper
- Expandable/collapsible abstracts
- Direct links to each paper on IEEE Xplore
- Editable journal list directly in the browser UI
- Dark-themed, responsive layout

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Zwl20085/UsefulToolLLM.git
cd UsefulToolLLM

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py
```

The browser opens automatically at **http://127.0.0.1:5000**.

### Command-line Options

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Interface to bind |
| `--port` | `5000` | Port to listen on |
| `--no-browser` | off | Skip auto-opening the browser |

```bash
python main.py --port 8080 --no-browser
```

### Default Journals

The tool ships with these six IEEE Transactions pre-configured:

| URL | Journal |
|-----|---------|
| `isnumber=4387790` | IEEE Transactions on Neural Networks and Learning Systems |
| `isnumber=4358729` | IEEE Transactions on Image Processing |
| `isnumber=4957013` | IEEE Transactions on Cybernetics |
| `isnumber=7098407` | IEEE Transactions on Industrial Informatics |
| `isnumber=4359240` | IEEE Transactions on Fuzzy Systems |
| `isnumber=4785241` | IEEE Transactions on Emerging Topics in Computing |

You can add, remove, or replace any URLs directly in the web UI without restarting.

### Project Structure

```
UsefulToolLLM/
├── ieee_early_access/
│   ├── __init__.py
│   ├── scraper.py          # IEEE Xplore REST API client
│   ├── server.py           # Flask web server
│   └── templates/
│       └── index.html      # Single-page UI
├── main.py                 # CLI entry point
├── requirements.txt
├── README.md
└── CLAUDE.md
```

### How It Works

1. `scraper.py` fetches each journal's TOC page to extract the **publication number** (punumber).
2. It queries the IEEE Xplore REST API (`/rest/search`) with `earlyAccess=True` and `sortType=newest`.
3. `server.py` exposes a `/fetch` POST endpoint consumed by the browser UI.
4. The UI renders results grouped by journal with expandable abstracts.

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Could not determine publication number" | Check that the URL is a valid IEEE Xplore TOC page |
| Empty paper list for a journal | The journal may have no current early-access articles |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside your venv |
| Port already in use | Use `--port 8080` (or another free port) |

---

## Contributing

Pull requests are welcome. Please open an issue first for major changes.

## License

MIT
