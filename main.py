"""
Rechtsprechungs-Agent
Durchsucht deutsche Gerichtsdatenbanken (Bund + alle Bundeslaender) und erstellt
eine juristische Zusammenfassung mit Claude.
"""

import argparse
import asyncio
import io
import sys
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

# Maximale Treffer pro Portal (verhindert Überlastung)
MAX_TREFFER_PRO_PORTAL = 5

# Pause zwischen Portalen in Sekunden (höfliches Crawling)
PAUSE_SEKUNDEN = 2.0


# ── Haupt-Agent ───────────────────────────────────────────────────────────────

async def agent(
    suchbegriff: str,
    nur_portale: list[str] | None = None,
    datum_von: str | None = None,
    datum_bis: str | None = None,
    gerichtstyp: str | None = None,
    anweisung: str | None = None,
    max_treffer: int = MAX_TREFFER_PRO_PORTAL,
    on_progress=None,  # callable(portal_name, status, treffer_count)
) -> dict:
    """
    Durchsucht alle konfigurierten Portale.
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
    print(f"{'='*60}\n")

    alle_treffer: list[dict] = []
    fehler: list[dict] = []

    for portal in portale:
        print(f"  >> Suche in {portal['name']} ...")
        if on_progress:
            on_progress(portal["name"], "running", None)
        try:
            treffer = await portal["funktion"](
                suchbegriff=suchbegriff,
                max_treffer=max_treffer,
                datum_von=datum_von,
                datum_bis=datum_bis,
            )
            for t in treffer:
                t["portal"] = portal["name"]
            # Gerichtstyp-Filter
            if gerichtstyp:
                gt = gerichtstyp.strip().upper()
                treffer = [
                    t for t in treffer
                    if gt in (t.get("gericht") or "").upper()
                    or gt in (t.get("aktenzeichen") or "").upper()
                    or gt in (t.get("titel") or "").upper()
                ]
            alle_treffer.extend(treffer)
            print(f"     {len(treffer)} Treffer gefunden.")
            if on_progress:
                on_progress(portal["name"], "ok", len(treffer))
        except Exception as e:
            print(f"     FEHLER: {e}")
            fehler.append({"portal": portal["name"], "fehler": str(e)})
            if on_progress:
                on_progress(portal["name"], "error", 0)

        await asyncio.sleep(PAUSE_SEKUNDEN)

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
    zusammenfassung = await erstelle_zusammenfassung(
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
    parser.add_argument("suchbegriff", nargs="*", help="Suchbegriff, auch mehrere Woerter (interaktiv wenn weggelassen)")
    parser.add_argument("--von",      metavar="TT.MM.JJJJ", help="Datum von (z.B. 01.01.2024)")
    parser.add_argument("--bis",      metavar="TT.MM.JJJJ", help="Datum bis (z.B. 31.12.2024)")
    parser.add_argument("--portale",  metavar="NAME", nargs="+",
                        help="Nur diese Portale durchsuchen (z.B. --portale Bund Bayern NRW)")
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

    ergebnis = asyncio.run(agent(
        suchbegriff=begriff,
        nur_portale=args.portale,
        datum_von=args.von,
        datum_bis=args.bis,
        max_treffer=args.treffer,
    ))

    # Ausgabe in Konsole
    print("\n" + "="*60)
    print("  ZUSAMMENFASSUNG")
    print("="*60)
    print(ergebnis["zusammenfassung"])

    # Ausgabe in Datei
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
