"""
Scraper für Bremen – 4 Gerichte:
  - Oberlandesgericht Bremen (OLG)
  - Oberverwaltungsgericht Bremen (OVG)
  - Verwaltungsgericht Bremen (VG)
  - Landesarbeitsgericht Bremen (LAG)

Jede Suche liefert chronologisch absteigende Ergebnisse.
Kein Datum-Filter möglich; es werden je Gericht maximal 10 Einträge
der ersten Ergebnisseite ausgewertet (= aktuellste Entscheidungen).
"""

import re
from playwright.async_api import async_playwright

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

# Pro Gericht maximal 10 Treffer (= erste Seite, neueste zuerst)
_MAX_PRO_GERICHT = 10


async def _suche_gericht(page, gericht: dict, suchbegriff: str) -> list[dict]:
    """Durchsucht ein einzelnes Bremer Gericht und gibt bis zu 10 Treffer zurück."""
    treffer = []
    try:
        await page.goto(gericht["url"], wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        # Volltext-Checkbox suchen und ankreuzen (verschiedene mögliche Selektoren)
        for sel in [
            "input[type='checkbox'][id*='volltext']",
            "input[type='checkbox'][name*='volltext']",
            "input[type='checkbox'][value*='volltext']",
            "input[type='checkbox'][id*='Volltext']",
            "input[type='checkbox'][name*='Volltext']",
            "label:has-text('Volltext') input[type='checkbox']",
        ]:
            try:
                cb = page.locator(sel).first
                if await cb.count() > 0:
                    if not await cb.is_checked():
                        await cb.check()
                    break
            except Exception:
                continue

        # Suchfeld füllen – typische Selektoren für Bremer Gerichts-CMS
        eingabe_gesetzt = False
        for sel in [
            "input[name='search[text]']",
            "input[name='searchword']",
            "input[id*='search']",
            "input[type='text']",
            "input[type='search']",
        ]:
            try:
                inp = page.locator(sel).first
                if await inp.count() > 0:
                    await inp.fill(suchbegriff)
                    eingabe_gesetzt = True
                    break
            except Exception:
                continue

        if not eingabe_gesetzt:
            return []

        # Formular absenden
        for sel in [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Suchen')",
            "button:has-text('suchen')",
            "input[value='Suchen']",
        ]:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0:
                    await btn.click()
                    break
            except Exception:
                continue

        await page.wait_for_timeout(3000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # Ergebnis-Links parsen
        # Typisches Muster: Links mit Aktenzeichen oder Datum im Text
        links = await page.query_selector_all("a")
        gesehen: set[str] = set()

        for link in links:
            if len(treffer) >= _MAX_PRO_GERICHT:
                break
            try:
                text = (await link.inner_text()).strip()
                href = await link.get_attribute("href") or ""
                if not href or href in gesehen or len(text) < 5:
                    continue
                # Nur interne Links der gleichen Domain
                if href.startswith("http") and gericht["base"] not in href:
                    continue
                if not href.startswith("http"):
                    href = gericht["base"] + (href if href.startswith("/") else "/" + href)

                # Entscheidungs-Links erkennen:
                # Aktenzeichen-Muster (z.B. "2 U 12/24"), Datum oder "/entscheidung" im Pfad
                ist_entscheidung = (
                    re.search(r"\d+\s+[A-Za-z]", text)
                    or re.search(r"\d{2}\.\d{2}\.\d{4}", text)
                    or re.search(r"/entscheidung", href, re.IGNORECASE)
                    or re.search(r"/beschluss|/urteil|/bescheid", href, re.IGNORECASE)
                )
                if not ist_entscheidung:
                    continue

                gesehen.add(href)

                # Metadaten aus Linktext extrahieren
                datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                datum_str = datum_m.group(1) if datum_m else ""

                az_m = re.search(r"\b(\d+\s+[A-Za-z]+\s+\d+/\d+)", text)
                az_str = az_m.group(1) if az_m else ""

                treffer.append({
                    "titel": text[:200],
                    "url": href,
                    "gericht": gericht["name"],
                    "datum": datum_str,
                    "aktenzeichen": az_str,
                    "vorschau": text[:500],
                })
            except Exception:
                continue

        # Fallback: Falls keine typischen Entscheidungs-Links gefunden,
        # alle Links aus einem Suchergebnis-Container nehmen
        if not treffer:
            for sel in [
                ".search-results a",
                ".result a",
                "article a",
                ".items-row a",
                "table.category td a",
                "#search-results a",
            ]:
                try:
                    elems = await page.query_selector_all(sel)
                    for el in elems[:_MAX_PRO_GERICHT]:
                        text = (await el.inner_text()).strip()
                        href = await el.get_attribute("href") or ""
                        if not href or len(text) < 5:
                            continue
                        if not href.startswith("http"):
                            href = gericht["base"] + (href if href.startswith("/") else "/" + href)
                        if href in gesehen:
                            continue
                        gesehen.add(href)
                        datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                        treffer.append({
                            "titel": text[:200],
                            "url": href,
                            "gericht": gericht["name"],
                            "datum": datum_m.group(1) if datum_m else "",
                            "aktenzeichen": "",
                            "vorschau": text[:500],
                        })
                    if treffer:
                        break
                except Exception:
                    continue

    except Exception as e:
        raise RuntimeError(f"Bremen/{gericht['name']}: {e}")

    return treffer


async def suche_bremen(
    suchbegriff,
    max_treffer=10,
    datum_von=None,
    datum_bis=None,
    gericht=None,
):
    """
    Durchsucht alle 4 Bremer Gerichte.
    Liefert je Gericht bis zu 10 Treffer (erste Seite, aktuellste Entscheidungen).
    Datum-Filter ist im Portal nicht verfügbar und wird ignoriert.
    """
    alle_treffer: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        try:
            for g in _GERICHTE:
                page = await context.new_page()
                try:
                    gefunden = await _suche_gericht(page, g, suchbegriff)
                    alle_treffer.extend(gefunden)
                except Exception as e:
                    # Einzelnes Gericht fehlgeschlagen → nicht den ganzen Scraper abbrechen
                    print(f"    [Bremen] {g['name']} übersprungen: {e}")
                finally:
                    await page.close()

                # Gesamtlimit beachten
                if max_treffer and len(alle_treffer) >= max_treffer:
                    break

        finally:
            await browser.close()

    return alle_treffer[:max_treffer] if max_treffer else alle_treffer
