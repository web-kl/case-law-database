from playwright.async_api import async_playwright
from .utils import suche_juris3

async def suche_rlp(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        try:
            return await suche_juris3(
                page, "bsrp", "https://www.landesrecht.rlp.de",
                suchbegriff, max_treffer, datum_von, datum_bis
            )
        except Exception as e:
            raise RuntimeError(f"RLP-Suche fehlgeschlagen: {e}")
        finally:
            await browser.close()
