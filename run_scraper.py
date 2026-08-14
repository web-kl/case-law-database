"""
Läuft als isolierter Subprocess für einen einzigen Portal-Aufruf.
Vermeidet Playwright-Windows-Assertion (process_title / IOCP) dauerhaft:
jeder Scraper bekommt seinen eigenen frischen Python-Prozess.

Aufruf: python run_scraper.py <portal_name> <params_json>
Ausgabe: JSON-Array der Treffer auf stdout (UTF-8)
Fehler:  Fehlermeldung auf stderr, Exit-Code 1
"""
import io
import importlib
import json
import os
import sys

# Projekt-Verzeichnis sicherstellen
_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

# Windows UTF-8
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRAPER_MAP = {
    "Bund":                   ("scrapers.bund",          "suche_bund"),
    "Brandenburg":            ("scrapers.brandenburg",   "suche_brandenburg"),
    "NRW":                    ("scrapers.nrw",           "suche_nrw"),
    "Bayern":                 ("scrapers.bayern",        "suche_bayern"),
    "Niedersachsen":          ("scrapers.niedersachsen", "suche_niedersachsen"),
    "Baden-Wuerttemberg":     ("scrapers.bw",            "suche_bw"),
    "Berlin":                 ("scrapers.berlin",        "suche_berlin"),
    "Bremen":                 ("scrapers.bremen",        "suche_bremen"),
    "Hamburg":                ("scrapers.hamburg",       "suche_hamburg"),
    "Hessen":                 ("scrapers.hessen",        "suche_hessen"),
    "Mecklenburg-Vorpommern": ("scrapers.mv",            "suche_mv"),
    "Rheinland-Pfalz":        ("scrapers.rlp",           "suche_rlp"),
    "Saarland":               ("scrapers.saarland",      "suche_saarland"),
    "Sachsen":                ("scrapers.sachsen",       "suche_sachsen"),
    "Sachsen-Anhalt":         ("scrapers.sachsen_anhalt","suche_sachsen_anhalt"),
    "Schleswig-Holstein":     ("scrapers.sh",            "suche_sh"),
    "Thueringen":             ("scrapers.thueringen",    "suche_thueringen"),
}

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Fehler: run_scraper.py <portal_name> <params_json>", file=sys.stderr)
        sys.exit(1)

    portal_name = sys.argv[1]
    params      = json.loads(sys.argv[2])

    if portal_name not in SCRAPER_MAP:
        print(f"Fehler: Unbekanntes Portal '{portal_name}'", file=sys.stderr)
        sys.exit(1)

    module_name, func_name = SCRAPER_MAP[portal_name]
    module = importlib.import_module(module_name)
    fn = getattr(module, func_name)

    # Stdout auf stderr umleiten, damit print()-Aufrufe in Scrapern
    # (z.B. Debug-/Fehlermeldungen) die JSON-Ausgabe nicht korrumpieren.
    _real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        result = fn(**params)
    except Exception as e:
        print(f"Scraper-Fehler: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        sys.stdout = _real_stdout

    print(json.dumps(result, ensure_ascii=False))
