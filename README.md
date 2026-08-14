# Rechtsprechungs-Agent

Durchsucht automatisch **17 deutsche Gerichtsdatenbanken** (Bund + alle Bundesländer)
und erstellt strukturierte juristische Zusammenfassungen sowie Blogbeiträge mit Claude (Anthropic).

## Features

- 🔍 **17 Portale** – Bund, alle 16 Bundesländer
- 🌐 **Web-UI** – Browser-Interface auf `http://localhost:8765`
- 📋 **Vorlagen** – vordefinierte Suchanfragen (Tagesüberblick, IT-Recht & Blog, …)
- 📝 **Zusammenfassung** – strukturierte juristische Analyse mit Claude
- 📰 **Blogbeitrag** – laienverständlicher Beitrag inkl. Titel und Meta-Description
- 💬 **Folgefragen** – Konversation über gefundene Entscheidungen
- 📅 **Datum-Filter** – Einschränkung auf Zeiträume
- ⚖️ **Gerichtstyp-Filter** – z. B. nur OLG, VG, LAG
- 🔢 **Treffermengen** – konfigurierbar pro Portal und gesamt

## Abgedeckte Datenbanken

| Portal | URL | Datenbank-Typ |
|---|---|---|
| **Bund** | rechtsprechung-im-internet.de | Formular (Playwright) |
| **Baden-Württemberg** | landesrecht-bw.de | juris3 REST-API |
| **Bayern** | gesetze-bayern.de | Formular (Playwright) |
| **Berlin** | gesetze.berlin.de | juris3 REST-API |
| **Brandenburg** | gerichtsentscheidungen.brandenburg.de | Formular (Playwright) |
| **Bremen** | OLG, OVG, VG, LAG (4 Portale) | Formular (Playwright) |
| **Hamburg** | landesrecht-hamburg.de | juris3 REST-API |
| **Hessen** | lareda.hessenrecht.hessen.de | juris3 REST-API |
| **Mecklenburg-Vorpommern** | landesrecht-mv.de | juris3 REST-API |
| **Niedersachsen** | voris.wolterskluwer-online.de | URL-Parameter (Playwright) |
| **NRW** | nrwesuche.justiz.nrw.de | Formular (Playwright) |
| **Rheinland-Pfalz** | landesrecht.rlp.de | juris3 REST-API |
| **Saarland** | recht.saarland.de | juris3 REST-API |
| **Sachsen** | esamosplus + OVG-Portal (2 Portale) | Formular (Playwright) |
| **Sachsen-Anhalt** | landesrecht.sachsen-anhalt.de | juris3 REST-API |
| **Schleswig-Holstein** | gesetze-rechtsprechung.sh.juris.de | juris3 REST-API |
| **Thüringen** | landesrecht.thueringen.de | juris3 REST-API |

## Voraussetzungen

- Python 3.11 oder neuer
- Anthropic API-Key ([console.anthropic.com](https://console.anthropic.com/))

## Installation

### 1. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Playwright-Browser installieren (einmalig)

```bash
playwright install chromium
```

### 3. API-Key konfigurieren

Datei `.env` im Projektverzeichnis anlegen:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Alternativ als Umgebungsvariable:

```powershell
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."
```

## Starten

### Windows (empfohlen)

```
start.bat
```

Öffnet automatisch das Konsolenfenster und den Browser auf `http://localhost:8765`.

### Manuell

```bash
python server.py
```

Dann Browser öffnen: `http://localhost:8765`

## Bedienung

### Suche starten

1. **Suchbegriff** eingeben oder eine **Vorlage** auswählen
2. Optional: Datum von/bis, Gerichtstyp, Portale einschränken
3. **Suche starten** klicken – die Portale werden live abgehakt
4. Nach Abschluss erscheint die **juristische Zusammenfassung**

### Vorlagen

| Vorlage | Beschreibung |
|---|---|
| 📅 Tagesüberblick | Neueste Entscheidungen der letzten 7 Tage |
| 💻 IT-Recht & Blog | Alle interessanten Urteile + Fokus auf DSGVO, KI, IT |

### Blogbeitrag erstellen

Nach einer Suche: Button **„Blogbeitrag erstellen"** → Claude erstellt einen
laienverständlichen Beitrag mit Titel und Meta-Description (via Anthropic Tool Use).

### Folgefragen

Im Eingabefeld unterhalb der Zusammenfassung weitere Fragen zu den
gefundenen Entscheidungen stellen. Claude antwortet auf Basis der Treffer.

## Treffermengen

| Feld | Bedeutung |
|---|---|
| **Treffer je Portal** | Max. Treffer pro Datenbank (0 = unbegrenzt, max. 100) |
| **Gesamtlimit** | Stopp wenn diese Zahl über alle Portale erreicht ist (0 = kein Limit) |

## Projektstruktur

```
rechtsprechung_agent/
├── server.py              # HTTP-Server (localhost:8765)
├── main.py                # Agenten-Steuerung, Portal-Liste
├── run_scraper.py         # Subprocess-Wrapper für Playwright (Windows-Fix)
├── summarizer.py          # Claude API (Zusammenfassung, Blog, Folgefragen)
├── prompt_parser.py       # Natürlichsprachliche Prompt-Analyse
├── start.bat              # Windows-Starter
├── .env                   # API-Key (nicht committen!)
├── requirements.txt
├── templates/
│   └── index.html         # Web-UI
├── scrapers/
│   ├── utils.py           # juris3 REST-API (generisch)
│   ├── bund.py
│   ├── bw.py
│   ├── bayern.py
│   ├── berlin.py
│   ├── brandenburg.py
│   ├── bremen.py          # 4 Bremer Gerichte
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
└── output/                # Ergebnisdateien (auto-erstellt)
```

## Neues Portal hinzufügen

### Scraper anlegen (`scrapers/meinland.py`)

```python
from playwright.sync_api import sync_playwright

def suche_meinland(
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
            # ... Scraping-Logik ...
            return [{
                "titel": "...",
                "url": "...",
                "gericht": "...",
                "datum": "TT.MM.JJJJ",
                "aktenzeichen": "...",
                "vorschau": "...",
            }]
        finally:
            browser.close()
```

### In `run_scraper.py` eintragen

```python
SCRAPER_MAP = {
    ...
    "Meinland": ("scrapers.meinland", "suche_meinland"),
}
```

### In `main.py` eintragen

```python
from scrapers.meinland import suche_meinland

PORTALE = [
    ...
    {"name": "Meinland", "funktion": suche_meinland},
]
```

## Technische Hinweise

### Warum Subprocesses?

Playwright's Node.js-Treiber verwendet libuv, das beim Start `GetConsoleTitleW()` aufruft.
Unter Windows schlägt dieser Aufruf fehl, wenn der Prozess in einem Thread (statt im
Haupt-Thread) gestartet wird – Ergebnis: `Assertion failed: process_title`.

Als Lösung wird jeder Scraper als eigener Python-Subprocess gestartet (`run_scraper.py`).
Jeder Subprocess bekommt seinen eigenen frischen Prozesskontext, in dem Playwright
problemlos startet.

### API-Limits

- juris3-Portale (REST-API): max. 100 Treffer pro Anfrage (API-seitige Begrenzung)
- Andere Portale: Begrenzung über `max_treffer`-Parameter (Listenkürzung)

## Rechtlicher Hinweis

Die abgerufenen Entscheidungen sind öffentlich zugängliche Gerichtsentscheidungen.
Die Nutzungsbedingungen der jeweiligen Portale sind zu beachten:

- **Juris-Portale** (Landesrecht-Portale): Nicht-gewerbliche Nutzung allgemein erlaubt.
- **Niedersachsen (Wolters Kluwer)**: Nicht-kommerzielles Text and Data Mining erlaubt
  nach § 44b UrhG. Kommerzielles TDM ausdrücklich ausgeschlossen.
- **Alle anderen Portale**: Öffentliche Gerichtsentscheidungen, Nutzung für eigene
  juristische Recherche.

Dieser Agent ist für eigene juristische Recherche konzipiert.
Für kommerzielle Weiterverwendung der Ergebnisse bitte die jeweiligen
Nutzungsbedingungen prüfen.
