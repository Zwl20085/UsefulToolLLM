# UsefulToolLLM

A collection of research productivity tools.

## Project Structure

```
UsefulToolLLM/
├── ieee_early_access/   # Tool 1: IEEE Early Access Paper Viewer (Flask)
├── image_cmap_gen/      # Tool 2: Image to Matplotlib Colormap Generator (Streamlit)
└── colorbar_to_svg/     # Tool 3: Colorbar Screenshot to Clean SVG (Streamlit)
```

---

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

### `image_cmap_gen/` — Image to Matplotlib Colormap Generator

Extract dominant colors from any image and turn them into a ready-to-use **matplotlib colormap** — with a live preview and one-click export.

#### Features

- Upload any PNG, JPEG, BMP, WebP, or TIFF image
- Extract 3–16 dominant colors via **KMeans** clustering (with PIL quantize fallback)
- Sort extracted colors by luminance, hue, or leave in cluster order
- Build a **linear** (smooth) or **listed** (discrete) matplotlib colormap
- Live 2-panel preview: gradient bar + sine-wave heatmap
- Export as a **self-contained `.py` snippet** (paste anywhere) or a **`.pickle`** file (load directly in Python)

#### Quick Start

```bash
cd image_cmap_gen

# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the app
streamlit run app.py
# → Opens http://localhost:8501 in your browser automatically
```

#### Project Structure

```
image_cmap_gen/
├── app.py               # Streamlit UI entry point
├── color_extractor.py   # KMeans / quantize color extraction + sorting
├── cmap_builder.py      # Build colormap & render previews
├── exporter.py          # Export as .py snippet or .pickle bytes
├── utils.py             # load_image, resize_for_processing
└── requirements.txt     # streamlit, Pillow, numpy, matplotlib, scikit-learn
```

#### How It Works

1. **Upload** an image — it is resized to ≤ 200 × 200 px before processing (fast, lossless for color extraction).
2. **KMeans** clusters all pixels into *N* colors; cluster centroids become the palette.
3. Colors are optionally sorted by perceptual **luminance** (`0.299R + 0.587G + 0.114B`) or **HSV hue**.
4. `LinearSegmentedColormap.from_list` / `ListedColormap` turns the palette into a standard matplotlib colormap.
5. A 2-panel preview (gradient bar + synthetic heatmap) lets you judge the colormap before exporting.

#### Export Formats

| Format | File | How to use |
|--------|------|------------|
| Python snippet | `<name>.py` | Copy-paste into any script; no external files needed |
| Pickle | `<name>.pkl` | `import pickle; cmap = pickle.load(open("name.pkl","rb"))` |

Both formats produce a standard `matplotlib.colors.Colormap` object compatible with `plt.imshow`, `plt.scatter`, `plt.colorbar`, etc.

---

### `colorbar_to_svg/` — Colorbar Screenshot to Clean SVG

Turn a **captured colorbar** from FE/CAE software (Abaqus, ANSYS, COMSOL) into a clean, publication-ready **SVG**. The post-processor's colorbar is auto-detected from a screenshot, and the usual wall of 12–15 tick values is replaced with a tidy **4–8 evenly-spaced labels**.

#### Features

- Upload a captured colorbar (PNG, JPEG, BMP, WebP, TIFF)
- **Auto-detects** the colored strip and its orientation (vertical or horizontal) — no manual cropping needed in the common case
- Manual region sliders + flip control to fix imperfect captures
- You enter the **value range** (min, max, linear or log scale); no fragile OCR
- Reduces labels to a clean **4–8 evenly-spaced** set with sensible number formatting (significant figures / scientific notation)
- **Smooth gradient** or **discrete blocks** SVG output, with optional title and units
- Live preview; one-click **SVG download** (scalable, editable in Inkscape/Illustrator)

#### Quick Start

```bash
cd colorbar_to_svg

# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch the app
streamlit run app.py
# → Opens http://localhost:8501 in your browser automatically
```

#### Project Structure

```
colorbar_to_svg/
├── app.py             # Streamlit UI entry point
├── strip_detector.py  # Auto-detect the colored strip (chroma-based) + orientation
├── sampler.py         # Sample ordered colors along the strip (median across width)
├── ticks.py           # Linear/log evenly-spaced tick values + number formatting
├── svg_builder.py     # Hand-built SVG colorbar + matching raster preview
├── utils.py           # load_image, resize_for_processing
└── requirements.txt   # streamlit, Pillow, numpy
```

#### How It Works

1. **Upload** a colorbar screenshot.
2. The strip is located by **chroma** (`max(R,G,B) − min(R,G,B)`) — background, gray and text score ~0, while even dark-but-saturated colors stay high. Projection profiles give the bounding box and orientation.
3. Colors are **sampled along the long axis** using a median across the short axis, so intruding tick marks, labels and borders are rejected.
4. You enter min/max and pick linear or log; the tool generates **4–8 evenly-spaced** labels (min at the bottom for vertical bars, at the left for horizontal — flip if needed).
5. A clean **SVG** is assembled (smooth `linearGradient` or discrete `rect` blocks) with tick marks, labels and an optional title/units.

> No OCR is used — reading tiny tick fonts off screenshots is unreliable, so the numeric range is entered manually and labels are regenerated exactly.

---

## Roadmap

- [ ] arXiv paper fetcher
- [ ] Google Scholar citation alert aggregator
- [ ] Semantic Scholar related-work explorer

## Contributing

PRs welcome. Please open an issue first for large changes.

## License

MIT
