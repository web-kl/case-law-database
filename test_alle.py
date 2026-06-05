import asyncio
from scrapers.bund import suche_bund
from scrapers.brandenburg import suche_brandenburg
from scrapers.nrw import suche_nrw
from scrapers.bayern import suche_bayern
from scrapers.niedersachsen import suche_niedersachsen
from scrapers.bw import suche_bw
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

PORTALE = [
    ("Bund",                  suche_bund),
    ("Brandenburg",           suche_brandenburg),
    ("NRW",                   suche_nrw),
    ("Bayern",                suche_bayern),
    ("Niedersachsen",         suche_niedersachsen),
    ("Baden-Wuerttemberg",    suche_bw),
    ("Berlin",                suche_berlin),
    ("Bremen",                suche_bremen),
    ("Hamburg",               suche_hamburg),
    ("Hessen",                suche_hessen),
    ("Mecklenburg-Vorpommern",suche_mv),
    ("Rheinland-Pfalz",       suche_rlp),
    ("Saarland",              suche_saarland),
    ("Sachsen",               suche_sachsen),
    ("Sachsen-Anhalt",        suche_sachsen_anhalt),
    ("Schleswig-Holstein",    suche_sh),
    ("Thueringen",            suche_thueringen),
]

async def main():
    VON = "01.01.2026"
    BIS = "30.05.2026"
    BEGRIFF = "Mietvertrag Kuendigung"

    ok, fehler = [], []
    for name, fn in PORTALE:
        try:
            t = await fn(BEGRIFF, max_treffer=3, datum_von=VON, datum_bis=BIS)
            print(f"OK  {name:<25} {len(t)} Treffer")
            if t:
                print(f"    -> {t[0]['datum']} | {t[0]['gericht'][:50]} | {t[0]['aktenzeichen']}")
            ok.append(name)
        except Exception as e:
            print(f"ERR {name:<25} {str(e)[:80]}")
            fehler.append((name, str(e)[:80]))

    print()
    print(f"Ergebnis: {len(ok)}/17 OK, {len(fehler)} Fehler")
    if fehler:
        for n, e in fehler:
            print(f"  FEHLER {n}: {e}")

asyncio.run(main())
