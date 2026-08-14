"""
Scraper für Bremen – 4 Gerichte:
  - Oberlandesgericht Bremen (OLG)
  - Oberverwaltungsgericht Bremen (OVG)
  - Verwaltungsgericht Bremen (VG)
  - Landesarbeitsgericht Bremen (LAG)

Je Gericht werden max. 10 Treffer der ersten Ergebnisseite ausgewertet
(chronologisch absteigend = aktuellste zuerst).
Kein Datum-Filter möglich.
"""
import re
from playwright.sync_api import sync_playwright

_GERICHTE = [
    {
        "name": "Oberlandesgericht Bremen",
        "url":  "https://www.oberlandesgericht.bremen.de/entscheidungen/entscheidungssuche-2337",
        "base": "https://www.oberlandesgericht.bremen.de",
    },
    {
        "name": "Oberverwaltungsgericht Bremen",
        "url":  "https://www.oberverwaltungsgericht.bremen.de/entscheidungen/entscheidungssuche-11266",
        "base": "https://www.oberverwaltungsgericht.bremen.de",
    },
    {
        "name": "Verwaltungsgericht Bremen",
        "url":  "https://www.verwaltungsgericht.bremen.de/entscheidungen/entscheidungssuche-12796",
        "base": "https://www.verwaltungsgericht.bremen.de",
    },
    {
        "name": "Landesarbeitsgericht Bremen",
        "url":  "https://www.landesarbeitsgericht.bremen.de/entscheidungen/entscheidungssuche-11509",
        "base": "https://www.landesarbeitsgericht.bremen.de",
    },
]

_MAX_PRO_GERICHT = 10


def _suche_gericht(page, gericht: dict, suchbegriff: str) -> list[dict]:
    treffer = []
    try:
        page.goto(gericht["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # Volltext-Checkbox ankreuzen
        for sel in [
            "input[type='checkbox'][id*='volltext']",
            "input[type='checkbox'][name*='volltext']",
            "input[type='checkbox'][value*='volltext']",
            "input[type='checkbox'][id*='Volltext']",
            "input[type='checkbox'][name*='Volltext']",
        ]:
            try:
                cb = page.locator(sel).first
                if cb.count() > 0:
                    if not cb.is_checked():
                        cb.check()
                    break
            except Exception:
                continue

        # Suchfeld füllen
        eingabe_gesetzt = False
        for sel in [
            "input[name='search[text]']", "input[name='searchword']",
            "input[id*='search']", "input[type='text']", "input[type='search']",
        ]:
            try:
                inp = page.locator(sel).first
                if inp.count() > 0:
                    inp.fill(suchbegriff)
                    eingabe_gesetzt = True
                    break
            except Exception:
                continue

        if not eingabe_gesetzt:
            return []

        # Formular absenden
        for sel in [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Suchen')", "input[value='Suchen']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click()
                    break
            except Exception:
                continue

        page.wait_for_timeout(3000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        links = page.query_selector_all("a")
        gesehen: set[str] = set()

        for link in links:
            if len(treffer) >= _MAX_PRO_GERICHT:
                break
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                if not href or href in gesehen or len(text) < 5:
                    continue
                if href.startswith("http") and gericht["base"] not in href:
                    continue
                if not href.startswith("http"):
                    href = gericht["base"] + (href if href.startswith("/") else "/" + href)

                ist_entscheidung = (
                    re.search(r"\d+\s+[A-Za-z]", text)
                    or re.search(r"\d{2}\.\d{2}\.\d{4}", text)
                    or re.search(r"/entscheidung", href, re.IGNORECASE)
                    or re.search(r"/beschluss|/urteil", href, re.IGNORECASE)
                )
                if not ist_entscheidung:
                    continue

                gesehen.add(href)
                datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                az_m    = re.search(r"\b(\d+\s+[A-Za-z]+\s+\d+/\d+)", text)
                treffer.append({
                    "titel":        text[:200],
                    "url":          href,
                    "gericht":      gericht["name"],
                    "datum":        datum_m.group(1) if datum_m else "",
                    "aktenzeichen": az_m.group(1) if az_m else "",
                    "vorschau":     text[:500],
                })
            except Exception:
                continue

        # Fallback: generische Container
        if not treffer:
            for sel in [".search-results a", ".result a", "article a",
                        ".items-row a", "table.category td a"]:
                try:
                    elems = page.query_selector_all(sel)
                    for el in elems[:_MAX_PRO_GERICHT]:
                        text = el.inner_text().strip()
                        href = el.get_attribute("href") or ""
                        if not href or len(text) < 5 or href in gesehen:
                            continue
                        if not href.startswith("http"):
                            href = gericht["base"] + (href if href.startswith("/") else "/" + href)
                        gesehen.add(href)
                        datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                        treffer.append({
                            "titel":        text[:200],
                            "url":          href,
                            "gericht":      gericht["name"],
                            "datum":        datum_m.group(1) if datum_m else "",
                            "aktenzeichen": "",
                            "vorschau":     text[:500],
                        })
                    if treffer:
                        break
                except Exception:
                    continue

    except Exception as e:
        raise RuntimeError(f"Bremen/{gericht['name']}: {e}")

    return treffer


def suche_bremen(
    suchbegriff,
    max_treffer=10,
    datum_von=None,
    datum_bis=None,
    gericht=None,
):
    """Durchsucht alle 4 Bremer Gerichte."""
    alle_treffer: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for g in _GERICHTE:
                page = browser.new_page()
                try:
                    gefunden = _suche_gericht(page, g, suchbegriff)
                    alle_treffer.extend(gefunden)
                except Exception as e:
                    print(f"    [Bremen] {g['name']} übersprungen: {e}")
                finally:
                    page.close()

                if max_treffer and len(alle_treffer) >= max_treffer:
                    break
        finally:
            browser.close()

    return alle_treffer[:max_treffer] if max_treffer else alle_treffer
