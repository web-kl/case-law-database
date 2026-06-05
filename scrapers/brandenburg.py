from playwright.async_api import async_playwright
from scrapers.utils import parse_titel

BASE_URL = 'https://gerichtsentscheidungen.brandenburg.de/suche'

async def suche_brandenburg(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(BASE_URL, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_selector("input[name='input_fulltext']", timeout=30000)
            def _de_to_iso(d):
                if not d: return None
                try:
                    t, m, j = d.split(".")
                    return f"{j}-{m}-{t}"
                except Exception:
                    return None

            await page.fill("input[name='input_fulltext']", suchbegriff)
            if datum_von:
                await page.fill("input[name='input_date_promulgation_from']", _de_to_iso(datum_von))
            if datum_bis:
                await page.fill("input[name='input_date_promulgation_to']", _de_to_iso(datum_bis))
            await page.click("button[onclick='showResults()']")
            await page.wait_for_timeout(4000)
            links = await page.query_selector_all("a[href*='/gerichtsentscheidung/']")
            treffer = []
            for link in links[:max_treffer]:
                try:
                    titel = (await link.inner_text()).strip()
                    href  = await link.get_attribute('href') or ''
                    if not titel: continue
                    if not href.startswith('http'): href = 'https://gerichtsentscheidungen.brandenburg.de' + href
                    treffer.append({'titel': titel, 'url': href, **parse_titel(titel)})
                except: continue
            return treffer
        except Exception as e: raise RuntimeError(f'Brandenburg-Suche fehlgeschlagen: {e}')
        finally: await browser.close()