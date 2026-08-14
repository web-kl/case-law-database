# German Case Law Agent

Automatically searches **17 German court databases** (federal + all 16 states)
and generates structured legal summaries and blog posts using Claude (Anthropic).

## Features

- 🔍 **17 portals** – federal courts and all 16 German states
- 🌐 **Web UI** – browser interface at `http://localhost:8765`
- 📋 **Templates** – pre-defined searches (daily overview, IT law & blog, …)
- 📝 **Summaries** – structured legal analysis powered by Claude
- 📰 **Blog posts** – plain-language articles with title and meta description
- 💬 **Follow-up questions** – conversational Q&A about found decisions
- 📅 **Date filter** – restrict searches to specific time periods
- ⚖️ **Court type filter** – e.g. only OLG, VG, LAG
- 🔢 **Result limits** – configurable per portal and globally

## Covered Databases

| State / Portal | URL | Type |
|---|---|---|
| **Federal (Bund)** | rechtsprechung-im-internet.de | Form (Playwright) |
| **Baden-Württemberg** | landesrecht-bw.de | juris3 REST API |
| **Bavaria** | gesetze-bayern.de | Form (Playwright) |
| **Berlin** | gesetze.berlin.de | juris3 REST API |
| **Brandenburg** | gerichtsentscheidungen.brandenburg.de | Form (Playwright) |
| **Bremen** | OLG, OVG, VG, LAG (4 portals) | Form (Playwright) |
| **Hamburg** | landesrecht-hamburg.de | juris3 REST API |
| **Hesse** | lareda.hessenrecht.hessen.de | juris3 REST API |
| **Mecklenburg-Vorpommern** | landesrecht-mv.de | juris3 REST API |
| **Lower Saxony** | voris.wolterskluwer-online.de | URL params (Playwright) |
| **North Rhine-Westphalia** | nrwesuche.justiz.nrw.de | Form (Playwright) |
| **Rhineland-Palatinate** | landesrecht.rlp.de | juris3 REST API |
| **Saarland** | recht.saarland.de | juris3 REST API |
| **Saxony** | esamosplus + OVG portal (2 portals) | Form (Playwright) |
| **Saxony-Anhalt** | landesrecht.sachsen-anhalt.de | juris3 REST API |
| **Schleswig-Holstein** | gesetze-rechtsprechung.sh.juris.de | juris3 REST API |
| **Thuringia** | landesrecht.thueringen.de | juris3 REST API |

## Requirements

- Python 3.11 or newer
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))

## Installation

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright browser (once)

```bash
playwright install chromium
```

### 3. Configure API key

Create a `.env` file in the project directory:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Or set it as an environment variable:

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Starting the Application

### Windows (recommended)

```
start.bat
```

Opens the console window and browser at `http://localhost:8765` automatically.

### Manual

```bash
python server.py
```

Then open your browser at `http://localhost:8765`.

## Usage

### Running a search

1. Enter a **search term** or select a **template**
2. Optionally set date range, court type, or restrict to specific portals
3. Click **"Search"** – portals are checked off live as they complete
4. The **legal summary** appears when all portals are done

### Templates

| Template | Description |
|---|---|
| 📅 Daily Overview | Most recent decisions from the last 7 days |
| 💻 IT Law & Blog | All notable rulings with a focus on GDPR, AI Act, IT security |

### Blog post generation

After a search: click **"Create blog post"** → Claude generates a plain-language
article with title and meta description (via Anthropic Tool Use).

### Follow-up questions

Use the input field below the summary to ask further questions about the found
decisions. Claude answers based on the retrieved case law.

## Result Limits

| Field | Meaning |
|---|---|
| **Results per portal** | Max. results per database (0 = unlimited, max. 100) |
| **Global limit** | Stop once this total is reached across all portals (0 = no limit) |

## Project Structure

```
rechtsprechung_agent/
├── server.py              # HTTP server (localhost:8765)
├── main.py                # Agent logic, portal list
├── run_scraper.py         # Subprocess wrapper for Playwright (Windows fix)
├── summarizer.py          # Claude API (summary, blog post, follow-up)
├── prompt_parser.py       # Natural language prompt analysis
├── start.bat              # Windows launcher
├── .env                   # API key (do not commit!)
├── requirements.txt
├── templates/
│   └── index.html         # Web UI
├── scrapers/
│   ├── utils.py           # juris3 REST API (generic)
│   ├── bund.py
│   ├── bw.py
│   ├── bayern.py
│   ├── berlin.py
│   ├── brandenburg.py
│   ├── bremen.py          # 4 Bremen courts
│   ├── hamburg.py
│   ├── hessen.py
│   ├── mv.py
│   ├── niedersachsen.py
│   ├── nrw.py
│   ├── rlp.py
│   ├── saarland.py
│   ├── sachsen.py         # esamosplus + OVG
│   ├── sachsen_anhalt.py
│   ├── sh.py
│   └── thueringen.py
└── output/                # Result files (auto-created)
```

## Adding a New Portal

### 1. Create the scraper (`scrapers/mystate.py`)

```python
from playwright.sync_api import sync_playwright

def suche_mystate(
    suchbegriff: str,
    max_treffer: int = 10,
    datum_von=None,
    datum_bis=None,
    gericht=None,
) -> list[dict]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # ... scraping logic ...
            return [{
                "titel": "...",
                "url": "...",
                "gericht": "...",
                "datum": "DD.MM.YYYY",
                "aktenzeichen": "...",
                "vorschau": "...",
            }]
        finally:
            browser.close()
```

### 2. Register in `run_scraper.py`

```python
SCRAPER_MAP = {
    ...
    "MyState": ("scrapers.mystate", "suche_mystate"),
}
```

### 3. Register in `main.py`

```python
from scrapers.mystate import suche_mystate

PORTALE = [
    ...
    {"name": "MyState", "funktion": suche_mystate},
]
```

## Technical Notes

### Why subprocesses?

Playwright's Node.js driver uses libuv, which calls `GetConsoleTitleW()` on startup.
On Windows, this call fails when the process is launched from a background thread
rather than the main thread — resulting in `Assertion failed: process_title` in
`src/win/util.c`.

The solution: each scraper is launched as a separate Python subprocess via
`run_scraper.py`. Every subprocess gets its own clean process context in which
Playwright starts without issues.

### API limits

- juris3 portals (REST API): max. 100 results per request (API-side limit)
- Other portals: limited via the `max_treffer` parameter (list slicing)

## Legal Notice

The retrieved decisions are publicly available court rulings.
The terms of use of each portal apply:

- **juris portals** (state law portals): non-commercial use generally permitted.
- **Lower Saxony (Wolters Kluwer)**: non-commercial text and data mining permitted
  under § 44b UrhG. Commercial TDM explicitly excluded.
- **All other portals**: public court decisions, use for personal legal research.

This agent is intended for personal legal research.
For commercial use of the results, please review the respective terms of service.
