"""
Scraper für Bayern (BAYERN.RECHT)
Selektoren: aus HTML-Diagnose ermittelt (Mai 2026)
"""
from playwright.async_api import async_playwright
from .utils import parse_titel

async def suche_bayern(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto('https://www.gesetze-bayern.de/Search', wait_until='networkidle', timeout=30000)
            await page.fill("input[name='SearchFields.Content']", suchbegriff)
            await page.click("button[at-target='searchPanelBoxSubmit']")
            await page.wait_for_load_state('networkidle', timeout=30000)

            # Nur Rechtsprechung filtern
            rspr_link = await page.query_selector("a[href*='/Search/Filter/DOKTYP/rspr']")
            if rspr_link:
                await rspr_link.click()
                await page.wait_for_load_state('networkidle', timeout=30000)

            # Datum-Filter auf Ergebnisseite setzen
            if datum_von:
                dv_field = await page.query_selector("input[name='SearchFields.DatumVon']")
                if dv_field:
                    await dv_field.fill(datum_von)
            if datum_bis:
                db_field = await page.query_selector("input[name='SearchFields.DatumBis']")
                if db_field:
                    await db_field.fill(datum_bis)
            if datum_von or datum_bis:
                await page.click("button[at-target='searchPanelBoxSubmit']")
                await page.wait_for_load_state('networkidle', timeout=30000)

            links = await page.query_selector_all('p.hltitel a')
            treffer = []
            for link in links[:max_treffer]:
                try:
                    titel = (await link.inner_text()).strip()
                    href  = await link.get_attribute('href') or ''
                    if not titel: continue
                    if not href.startswith('http'): href = 'https://www.gesetze-bayern.de' + href
                    treffer.append({'titel': titel, 'url': href, **parse_titel(titel)})
                except: continue
            return treffer
        except Exception as e: raise RuntimeError(f'Bayern: {e}')
        finally: await browser.close()
