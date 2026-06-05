"""
Scraper für Bremen (OVG Bremen)
Hinweis: Nur Entscheidungen des Oberverwaltungsgerichts Bremen verfügbar.
Kein Datum-Filter im Portal unterstützt.
"""
import re
from urllib.parse import quote
from playwright.async_api import async_playwright

_BASE = "https://www.oberverwaltungsgericht.bremen.de/sixcms/detail.php"

def _matches_datum(text, datum_von, datum_bis):
    """Prüft ob ein Datum im Text im gewünschten Bereich liegt."""
    if not datum_von and not datum_bis:
        return True
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if not m:
        return True
    try:
        t, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if datum_von:
            tv, mv, jv = [int(x) for x in datum_von.split(".")]
            if (j, mo, t) < (jv, mv, tv):
                return False
        if datum_bis:
            tb, mb, jb = [int(x) for x in datum_bis.split(".")]
            if (j, mo, t) > (jb, mb, tb):
                return False
    except Exception:
        pass
    return True

async def suche_bremen(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    url = (f"{_BASE}?template=20_search_d"
           f"&search%5Bsend%5D=1"
           f"&search%5Bvt%5D={quote(suchbegriff)}"
           f"&lang=de")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)

            # Ergebnis-Links parsen
            links = await page.query_selector_all("a")
            treffer = []
            gesehen = set()

            for link in links:
                try:
                    text = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if not href or href in gesehen or len(text) < 5:
                        continue
                    if not href.startswith("http"):
                        href = "https://www.oberverwaltungsgericht.bremen.de" + href
                    # Nur Entscheidungs-Links (enthalten Aktenzeichen-Muster oder Datum)
                    if not (re.search(r"\d+\s+[A-Z]", text) or re.search(r"\d{2}\.\d{2}\.\d{4}", text)):
                        continue
                    if not _matches_datum(text, datum_von, datum_bis):
                        continue

                    gesehen.add(href)
                    meta_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                    datum_str = meta_m.group(1) if meta_m else ""
                    teile = text.split(",")
                    gericht_name = teile[0].strip() if teile else ""

                    treffer.append({
                        "titel": text[:200],
                        "url": href,
                        "gericht": gericht_name,
                        "datum": datum_str,
                        "aktenzeichen": "",
                        "vorschau": text[:500],
                    })
                    if len(treffer) >= max_treffer:
                        break
                except Exception:
                    continue

            return treffer
        except Exception as e:
            raise RuntimeError(f"Bremen-Suche fehlgeschlagen: {e}")
        finally:
            await browser.close()
