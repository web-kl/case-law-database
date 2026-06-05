"""
Scraper für Niedersachsen (NI-VORIS / Wolters Kluwer)
URL: https://voris.wolterskluwer-online.de/search
"""

import re
from urllib.parse import quote
from playwright.async_api import async_playwright

BASE_URL = "https://voris.wolterskluwer-online.de/search"
RSPR_FILTER = "publicationform-ats-filter!ATS_Rechtsprechung"


def _de_to_iso(d):
    if not d:
        return None
    try:
        t, m, j = d.split(".")
        return f"{j}-{m}-{t}"
    except Exception:
        return None


def _parse_titel(titel: str) -> dict:
    meta = {}
    m = re.search(r"\d{2}\.\d{2}\.\d{4}", titel)
    if m:
        meta["datum"] = m.group()
    m2 = re.search(r"-\s*(\d[\w\s/]+)\s*-", titel)
    if m2:
        meta["aktenzeichen"] = m2.group(1).strip()
    teile = titel.split(",")
    if teile:
        meta["gericht"] = teile[0].strip()
    return meta


async def suche_niedersachsen(
    suchbegriff: str,
    max_treffer: int = 5,
    datum_von: str | None = None,
    datum_bis: str | None = None,
    gericht: str | None = None,
) -> list[dict]:
    params = (
        f"query={quote(suchbegriff)}"
        f"&publicationtype={quote(RSPR_FILTER)}"
    )
    iso_von = _de_to_iso(datum_von)
    iso_bis = _de_to_iso(datum_bis)
    if iso_von:
        params += f"&date={quote(iso_von)}"
    if iso_bis:
        params += f"&end_date_range={quote(iso_bis)}"
    url = f"{BASE_URL}?{params}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            links = await page.query_selector_all("h3 a")
            treffer = []
            for link in links[:max_treffer]:
                try:
                    titel = (await link.inner_text()).strip()
                    if not titel:
                        continue
                    href = await link.get_attribute("href") or ""
                    if href and not href.startswith("http"):
                        href = "https://voris.wolterskluwer-online.de" + href
                    meta = _parse_titel(titel)
                    treffer.append({
                        "titel": titel,
                        "url": href,
                        "gericht": meta.get("gericht", ""),
                        "datum": meta.get("datum", ""),
                        "aktenzeichen": meta.get("aktenzeichen", ""),
                        "vorschau": titel[:500],
                    })
                except Exception:
                    continue
            return treffer
        except Exception as e:
            raise RuntimeError(f"Niedersachsen-Suche fehlgeschlagen: {e}") from e
        finally:
            await browser.close()
