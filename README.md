# Rechtsprechungs-Agent — POC

Durchsucht automatisch 4 deutsche Gerichtsdatenbanken und erstellt
eine juristische Zusammenfassung mit Claude (Anthropic).

## Abgedeckte Datenbanken

| Bundesland | URL | Typ |
|---|---|---|
| Brandenburg | gerichtsentscheidungen.brandenburg.de | Formular |
| NRW | nrwesuche.justiz.nrw.de | Formular |
| Bayern | gesetze-bayern.de | URL-Parameter |
| Niedersachsen | voris.wolterskluwer-online.de | URL-Parameter |

## Installation

### 1. Python-Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Playwright-Browser installieren (einmalig)

```bash
playwright install chromium
```

### 3. API-Key setzen

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-..."
```

Den API-Key erhalten Sie unter: https://console.anthropic.com/

## Verwendung

### Einfache Suche (interaktiv)

```bash
python main.py
```

### Suchbegriff als Argument

```bash
python main.py "Mietminderung Schimmel"
python main.py "Kündigung fristlos Arbeitnehmer"
python main.py "Werkvertragsrecht Mängel"
```

### Im Python-Code

```python
import asyncio
from main import agent

ergebnis = asyncio.run(agent(
    suchbegriff="Mietminderung Schimmel",
    nur_portale=["Bayern", "NRW"],   # None = alle 4
    datum_von="01.01.2023",          # optional
    datum_bis="31.12.2024",          # optional
))
print(ergebnis)
```

## Projektstruktur

```
rechtsprechung_agent/
├── main.py              # Einstiegspunkt + Steuerung
├── summarizer.py        # Claude API-Anbindung
├── requirements.txt     # Python-Abhängigkeiten
├── README.md
├── scrapers/
│   ├── __init__.py
│   ├── brandenburg.py   # Scraper Brandenburg
│   ├── nrw.py           # Scraper NRW
│   ├── bayern.py        # Scraper Bayern
│   └── niedersachsen.py # Scraper Niedersachsen
└── output/              # Ergebnisdateien (auto-erstellt)
```

## Weitere Portale ergänzen

Vorlage für einen neuen Scraper:

```python
# scrapers/meinbundesland.py
async def suche_meinbundesland(
    suchbegriff: str,
    max_treffer: int = 5,
    datum_von=None,
    datum_bis=None,
    gericht=None,
) -> list[dict]:
    # ... Playwright-Code ...
    return treffer  # Liste von Dicts: titel, url, gericht, datum, aktenzeichen, vorschau
```

Dann in `main.py` in die `PORTALE`-Liste eintragen.

## Rechtlicher Hinweis

- **Brandenburg, NRW, Bayern**: Nicht-gewerbliche Nutzung ausdrücklich erlaubt.
- **Niedersachsen (Wolters Kluwer)**: Nicht-kommerzielles Text und Data Mining
  erlaubt nach § 44b UrhG. Kommerzielles TDM ist ausdrücklich ausgeschlossen.

Dieser Agent ist für eigene juristische Recherche und Kanzleizwecke konzipiert.
Für kommerzielle Weiterverwendung der Ergebnisse bitte die jeweiligen
Nutzungsbedingungen prüfen.
