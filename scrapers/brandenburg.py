from playwright.sync_api import sync_playwright
from scrapers.utils import parse_titel

BASE_URL = 'https://gerichtsentscheidungen.brandenburg.de/suche'

def suche_brandenburg(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(BASE_URL, wait_until='domcontentloaded', timeout=60000)
            page.wait_for_selector("input[name='input_fulltext']", timeout=30000)

            def _de_to_iso(d):
                if not d: return None
                try:
                    t, m, j = d.split(".")
                    return f"{j}-{m}-{t}"
                except Exception:
                    return None

            page.fill("input[name='input_fulltext']", suchbegriff or "")
            if datum_von:
                page.fill("input[name='input_date_promulgation_from']", _de_to_iso(datum_von))
            if datum_bis:
                page.fill("input[name='input_date_promulgation_to']", _de_to_iso(datum_bis))
            page.click("button[onclick='showResults()']")
            page.wait_for_timeout(4000)
            links = page.query_selector_all("a[href*='/gerichtsentscheidung/']")
            treffer = []
            for link in links[:max_treffer]:
                try:
                    titel = link.inner_text().strip()
                    href  = link.get_attribute('href') or ''
                    if not titel: continue
                    if not href.startswith('http'): href = 'https://gerichtsentscheidungen.brandenburg.de' + href
                    treffer.append({'titel': titel, 'url': href, **parse_titel(titel)})
                except: continue
            return treffer
        except Exception as e: raise RuntimeError(f'Brandenburg-Suche fehlgeschlagen: {e}')
        finally: browser.close()
