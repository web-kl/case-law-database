import re
from playwright.async_api import async_playwright

BASE_URL = 'https://nrwesuche.justiz.nrw.de/'

async def suche_nrw(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(BASE_URL, wait_until='networkidle', timeout=60000)
            await page.wait_for_timeout(2000)
            await page.fill("input#text", suchbegriff)
            if datum_von:
                await page.evaluate(f"document.querySelector('input[name=\"von\"]').value = '{datum_von}'")
            if datum_bis:
                await page.evaluate(f"document.querySelector('input[name=\"bis\"]').value = '{datum_bis}'")
            await page.click("input#absenden")
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
            await page.wait_for_timeout(3000)

            ergebnisse = await page.query_selector_all("div.einErgebnis")
            treffer = []
            for div in ergebnisse[:max_treffer]:
                try:
                    link = await div.query_selector("a")
                    if not link:
                        continue
                    titel_text = (await link.inner_text()).strip()
                    href = await link.get_attribute("href") or ""
                    if not href.startswith("http"):
                        href = "https://nrwe.justiz.nrw.de" + href

                    # Metadaten aus dem Text des div
                    block_text = (await div.inner_text()).strip()
                    datum = ""
                    m = re.search(r"Entscheidungsdatum:\s*(\d{2}\.\d{2}\.\d{4})", block_text)
                    if m:
                        datum = m.group(1)
                    gericht_name = ""
                    m2 = re.search(r"Gericht:\s*(.+?)(?:\r|\n|Entscheidungsart)", block_text)
                    if m2:
                        gericht_name = m2.group(1).strip()
                    az = ""
                    m3 = re.search(r"Aktenzeichen:\s*(.+?)(?:\r|\n|ECLI)", block_text)
                    if m3:
                        az = m3.group(1).strip()

                    treffer.append({
                        "titel": titel_text,
                        "url": href,
                        "gericht": gericht_name,
                        "datum": datum,
                        "aktenzeichen": az,
                        "vorschau": block_text[:500],
                    })
                except Exception:
                    continue
            return treffer
        except Exception as e:
            raise RuntimeError(f'NRW-Suche fehlgeschlagen: {e}')
        finally:
            await browser.close()
