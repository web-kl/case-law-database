"""
Scraper für Bayern (BAYERN.RECHT)
"""
from playwright.sync_api import sync_playwright
from .utils import parse_titel

def suche_bayern(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto('https://www.gesetze-bayern.de/Search', wait_until='networkidle', timeout=30000)
            page.fill("input[name='SearchFields.Content']", suchbegriff)
            page.click("button[at-target='searchPanelBoxSubmit']")
            page.wait_for_load_state('networkidle', timeout=30000)

            # Nur Rechtsprechung filtern
            rspr_link = page.query_selector("a[href*='/Search/Filter/DOKTYP/rspr']")
            if rspr_link:
                rspr_link.click()
                page.wait_for_load_state('networkidle', timeout=30000)

            # Datum-Filter auf Ergebnisseite setzen
            if datum_von:
                dv_field = page.query_selector("input[name='SearchFields.DatumVon']")
                if dv_field:
                    dv_field.fill(datum_von)
            if datum_bis:
                db_field = page.query_selector("input[name='SearchFields.DatumBis']")
                if db_field:
                    db_field.fill(datum_bis)
            if datum_von or datum_bis:
                page.click("button[at-target='searchPanelBoxSubmit']")
                page.wait_for_load_state('networkidle', timeout=30000)

            links = page.query_selector_all('p.hltitel a')
            treffer = []
            for link in links[:max_treffer]:
                try:
                    titel = link.inner_text().strip()
                    href  = link.get_attribute('href') or ''
                    if not titel: continue
                    if not href.startswith('http'): href = 'https://www.gesetze-bayern.de' + href
                    treffer.append({'titel': titel, 'url': href, **parse_titel(titel)})
                except: continue
            return treffer
        except Exception as e: raise RuntimeError(f'Bayern: {e}')
        finally: browser.close()
