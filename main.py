"""
Rechtsprechungs-Agent
Durchsucht deutsche Gerichtsdatenbanken (Bund + alle Bundeslaender) und erstellt
eine juristische Zusammenfassung mit Claude.
Alle Scraper und die Claude-Zusammenfassung sind synchron – kein asyncio.
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

# Windows-Konsole auf UTF-8 umstellen
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from scrapers.brandenburg import suche_brandenburg
from scrapers.nrw import suche_nrw
from scrapers.bayern import suche_bayern
from scrapers.niedersachsen import suche_niedersachsen
from scrapers.bw import suche_bw
from scrapers.bund import suche_bund
from scrapers.berlin import suche_berlin
from scrapers.bremen import suche_bremen
from scrapers.hamburg import suche_hamburg
from scrapers.hessen import suche_hessen
from scrapers.mv import suche_mv
from scrapers.rlp import suche_rlp
from scrapers.saarland import suche_saarland
from scrapers.sachsen import suche_sachsen
from scrapers.sachsen_anhalt import suche_sachsen_anhalt
from scrapers.sh import suche_sh
from scrapers.thueringen import suche_thueringen
from summarizer import erstelle_zusammenfassung


# ── Konfiguration ─────────────────────────────────────────────────────────────

PORTALE = [
    {"name": "Bund",                  "funktion": suche_bund},
    {"name": "Brandenburg",           "funktion": suche_brandenburg},
    {"name": "NRW",                   "funktion": suche_nrw},
    {"name": "Bayern",                "funktion": suche_bayern},
    {"name": "Niedersachsen",         "funktion": suche_niedersachsen},
    {"name": "Baden-Wuerttemberg",    "funktion": suche_bw},
    {"name": "Berlin",                "funktion": suche_berlin},
    {"name": "Bremen",                "funktion": suche_bremen},
    {"name": "Hamburg",               "funktion": suche_hamburg},
    {"name": "Hessen",                "funktion": suche_hessen},
    {"name": "Mecklenburg-Vorpommern","funktion": suche_mv},
    {"name": "Rheinland-Pfalz",       "funktion": suche_rlp},
    {"name": "Saarland",              "funktion": suche_saarland},
    {"name": "Sachsen",               "funktion": suche_sachsen},
    {"name": "Sachsen-Anhalt",        "funktion": suche_sachsen_anhalt},
    {"name": "Schleswig-Holstein",    "funktion": suche_sh},
    {"name": "Thueringen",            "funktion": suche_thueringen},
]

MAX_TREFFER_PRO_PORTAL = 100

GERICHTSTYP_MAP: dict[str, list[str]] = {
    "SG":     ["sozialgericht", "landessozialgericht", "bundessozialgericht"],
    "LSG":    ["landessozialgericht"],
    "BSG":    ["bundessozialgericht"],
    "VG":     ["verwaltungsgericht", "oberverwaltungsgericht",
                "bundesverwaltungsgericht", "verwaltungsgerichtshof"],
    "OVG":    ["oberverwaltungsgericht"],
    "VGH":    ["verwaltungsgerichtshof"],
    "BVERWG": ["bundesverwaltungsgericht"],
    "FG":     ["finanzgericht", "bundesfinanzhof"],
    "BFH":    ["bundesfinanzhof"],
    "ARBG":   ["arbeitsgericht", "landesarbeitsgericht", "bundesarbeitsgericht"],
    "LAG":    ["landesarbeitsgericht"],
    "BAG":    ["bundesarbeitsgericht"],
    "AG":     ["amtsgericht", "landgericht", "oberlandesgericht", "bundesgerichtshof"],
    "LG":     ["landgericht"],
    "OLG":    ["oberlandesgericht"],
    "BGH":    ["bundesgerichtshof"],
    "AMTSG":  ["amtsgericht"],
    "VERFG":  ["verfassungsgericht", "verfassungsgerichtshof",
                "staatsgerichtshof", "bundesverfassungsgericht"],
    "BVERFG": ["bundesverfassungsgericht"],
}

PAUSE_SEKUNDEN = 2.0

# Pfad zum Subprocess-Skript
_SCRAPER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run_scraper.py")
_PROJECT_DIR    = os.path.dirname(os.path.abspath(__file__))


def _run_scraper_subprocess(
    portal_name: str,
    suchbegriff: str,
    max_treffer: int,
    datum_von,
    datum_bis,
) -> list[dict]:
    """
    Startet einen Scraper als eigenen Python-Prozess.
    Vermeidet Playwright-Windows-Assertion dauerhaft:
    kein geteilter Event-Loop, keine IOCP-Konflikte.
    """
    params = json.dumps({
        "suchbegriff": suchbegriff,
        "max_treffer":  max_treffer,
        "datum_von":    datum_von,
        "datum_bis":    datum_bis,
    }, ensure_ascii=False)

    proc = subprocess.run(
        [sys.executable, _SCRAPER_SCRIPT, portal_name, params],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        cwd=_PROJECT_DIR,
    )

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(err[:500] if err else "Subprocess fehlgeschlagen ohne Fehlermeldung")

    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError("Scraper-Subprocess hat keine Ausgabe geliefert")

    data = json.loads(stdout)
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(data["error"])
    return data


# ── Haupt-Agent ───────────────────────────────────────────────────────────────

def agent(
    suchbegriff: str,
    nur_portale: list[str] | None = None,
    datum_von: str | None = None,
    datum_bis: str | None = None,
    gerichtstyp: str | None = None,
    anweisung: str | None = None,
    max_treffer: int = MAX_TREFFER_PRO_PORTAL,
    max_treffer_gesamt: int | None = None,
    on_progress=None,
) -> dict:
    """
    Durchsucht alle konfigurierten Portale (synchron).
    Gibt dict zurück: {treffer: [...], zusammenfassung: str, fehler: [...]}
    """

    portale = PORTALE
    if nur_portale:
        portale = [p for p in PORTALE if p["name"] in nur_portale]

    print(f"\n{'='*60}")
    print(f"  Rechtsprechungs-Agent - Suche startet")
    print(f"  Suchbegriff : {suchbegriff}")
    if datum_von or datum_bis:
        print(f"  Zeitraum    : {datum_von or '?'} - {datum_bis or 'heute'}")
    if gerichtstyp:
        print(f"  Gerichtstyp : {gerichtstyp}")
    print(f"  Portale     : {', '.join(p['name'] for p in portale)}")
    if max_treffer_gesamt:
        print(f"  Max. gesamt : {max_treffer_gesamt}")
    print(f"{'='*60}\n")

    alle_treffer: list[dict] = []
    fehler: list[dict] = []

    gt_upper = gerichtstyp.strip().upper() if gerichtstyp else None
    gt_name_patterns = []
    if gt_upper:
        for name in GERICHTSTYP_MAP.get(gt_upper, []):
            gt_name_patterns.append(
                re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
            )

    def _gt_match(t: dict) -> bool:
        felder = [t.get("gericht") or "", t.get("aktenzeichen") or "", t.get("titel") or ""]
        felder_upper = [f.upper() for f in felder]
        if any(gt_upper in f for f in felder_upper):
            return True
        return any(pat.search(f) for pat in gt_name_patterns for f in felder)

    for portal in portale:
        print(f"  >> Suche in {portal['name']} ...")
        if on_progress:
            on_progress(portal["name"], "running", None)
        try:
            treffer = _run_scraper_subprocess(
                portal["name"],
                suchbegriff,
                max_treffer,
                datum_von,
                datum_bis,
            )
            for t in treffer:
                t["portal"] = portal["name"]
            if gerichtstyp:
                treffer = [t for t in treffer if _gt_match(t)]
            alle_treffer.extend(treffer)
            print(f"     {len(treffer)} Treffer gefunden.")
            if on_progress:
                on_progress(portal["name"], "ok", len(treffer))
        except Exception as e:
            print(f"     FEHLER: {e}")
            fehler.append({"portal": portal["name"], "fehler": str(e)})
            if on_progress:
                on_progress(portal["name"], "error", 0)

        if max_treffer_gesamt and len(alle_treffer) >= max_treffer_gesamt:
            print(f"  Gesamtlimit von {max_treffer_gesamt} Treffern erreicht, Suche gestoppt.")
            break

        time.sleep(PAUSE_SEKUNDEN)

    print(f"\n  Gesamt: {len(alle_treffer)} Treffer aus {len(portale)} Portalen.")

    if not alle_treffer:
        return {
            "treffer": [],
            "zusammenfassung": "Keine Ergebnisse gefunden. Bitte Suchbegriff oder Portale anpassen.",
            "fehler": fehler,
        }

    print("\n  Erstelle Zusammenfassung mit Claude ...")
    if on_progress:
        on_progress("__summary__", "running", None)
    zusammenfassung = erstelle_zusammenfassung(
        suchbegriff=suchbegriff,
        treffer=alle_treffer,
        anweisung=anweisung,
    )
    if on_progress:
        on_progress("__summary__", "ok", None)

    return {
        "treffer": alle_treffer,
        "zusammenfassung": zusammenfassung,
        "fehler": fehler,
    }


# ── Einstiegspunkt ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Rechtsprechungs-Agent — durchsucht deutsche Gerichtsdatenbanken",
    )
    parser.add_argument("suchbegriff", nargs="*", help="Suchbegriff")
    parser.add_argument("--von",      metavar="TT.MM.JJJJ", help="Datum von")
    parser.add_argument("--bis",      metavar="TT.MM.JJJJ", help="Datum bis")
    parser.add_argument("--portale",  metavar="NAME", nargs="+",
                        help="Nur diese Portale durchsuchen")
    parser.add_argument("--treffer",  metavar="N", type=int, default=MAX_TREFFER_PRO_PORTAL,
                        help=f"Max. Treffer pro Portal (Standard: {MAX_TREFFER_PRO_PORTAL})")
    args = parser.parse_args()

    if args.suchbegriff:
        begriff = " ".join(args.suchbegriff)
    else:
        print("\nRechtsprechungs-Agent")
        print("─────────────────────")
        begriff = input("Suchbegriff: ").strip()
        if not begriff:
            print("Kein Suchbegriff eingegeben. Abbruch.")
            sys.exit(1)

    ergebnis = agent(
        suchbegriff=begriff,
        nur_portale=args.portale,
        datum_von=args.von,
        datum_bis=args.bis,
        max_treffer=args.treffer,
    )

    print("\n" + "="*60)
    print("  ZUSAMMENFASSUNG")
    print("="*60)
    print(ergebnis["zusammenfassung"])

    zeitstempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    dateiname = f"output/zusammenfassung_{zeitstempel}.txt"
    with open(dateiname, "w", encoding="utf-8") as f:
        f.write(f"Suchbegriff: {begriff}\n")
        if args.von or args.bis:
            f.write(f"Zeitraum: {args.von or '?'} - {args.bis or 'heute'}\n")
        f.write(f"Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
        f.write("="*60 + "\n\n")
        f.write(ergebnis["zusammenfassung"])
    print(f"\n  Gespeichert unter: {dateiname}")
