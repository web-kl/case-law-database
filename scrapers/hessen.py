from playwright.sync_api import sync_playwright
from .utils import suche_juris3

def suche_hessen(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        )
        page = ctx.new_page()
        try:
            return suche_juris3(
                page, "bshe", "https://www.lareda.hessenrecht.hessen.de",
                suchbegriff, max_treffer, datum_von, datum_bis
            )
        except Exception as e:
            raise RuntimeError(f"Hessen-Suche fehlgeschlagen: {e}")
        finally:
            browser.close()
