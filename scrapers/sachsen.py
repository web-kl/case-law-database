"""
Scraper fur Sachsen (OLG Dresden - esamosplus)
Nur OLG Dresden verfugbar; kein eigenstandiger URL pro Entscheidung.
"""
import asyncio
from playwright.async_api import async_playwright

_BASE = "https://www.justiz.sachsen.de/esamosplus/pages/index.aspx"

async def suche_sachsen(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(_BASE, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(3000)

            frame = next((f for f in page.frames if "suchen.aspx" in f.url), None)
            if not frame:
                raise RuntimeError("Sachsen: suchen.aspx frame nicht gefunden")

            await frame.evaluate("""(args) => {
                var ta = document.querySelector('#DV13_C8');
                if(ta) { ta.readOnly = false; ta.value = args[0]; }
                var d1 = document.querySelector('#DV1_C34');
                var d2 = document.querySelector('#DV1_C35');
                if(d1 && args[1]) d1.value = args[1];
                if(d2 && args[2]) d2.value = args[2];
            }""", [suchbegriff, datum_von or "", datum_bis or ""])

            await frame.click("#DV1_C24", force=True)
            await page.wait_for_timeout(6000)

            frame2 = next((f for f in page.frames if "suchen.aspx" in f.url), None)
            if not frame2:
                raise RuntimeError("Sachsen: frame nach Suche nicht gefunden")

            rows_data = await frame2.evaluate("""() => {
                var rows = Array.from(document.querySelectorAll('input[id*="DV13_Table_ctl"]'));
                var grouped = {};
                rows.forEach(el => {
                    var m = el.id.match(/DV13_Table_ctl(\\d+)_DV13_Table_Col(\\d+)_C1/);
                    if(m) {
                        var row = m[1]; var col = m[2];
                        if(!grouped[row]) grouped[row] = {};
                        grouped[row][col] = el.value;
                    }
                });
                return grouped;
            }""")

            # Leitsatz des auto-selektierten ersten Ergebnisses lesen
            leitsatz_initial = await frame2.evaluate("""() => {
                var txt = document.body.innerText;
                var idx = txt.indexOf('Selektierte Entscheidung');
                if(idx < 0) return '';
                var after = txt.substring(idx + 24).trim();
                var end = after.indexOf('Suchergebnisse');
                return end > 0 ? after.substring(0, end).trim() : after.substring(0, 300).trim();
            }""")

            treffer = []
            for i, (row_key, cols) in enumerate(list(rows_data.items())[:max_treffer]):
                datum = cols.get("0", "")
                az = cols.get("1", "")
                gericht_name = cols.get("2", "Oberlandesgericht Dresden")
                # Leitsatz nur fuer erstes Ergebnis zuverlaessig; Rest: Metadaten als Vorschau
                vorschau = leitsatz_initial if i == 0 and leitsatz_initial else f"{az} vom {datum}"
                treffer.append({
                    "titel": f"{gericht_name}: {az} vom {datum}",
                    "url": _BASE,
                    "gericht": gericht_name,
                    "datum": datum,
                    "aktenzeichen": az,
                    "vorschau": vorschau[:500],
                })

            return treffer
        except Exception as e:
            raise RuntimeError(f"Sachsen-Suche fehlgeschlagen: {e}")
        finally:
            await browser.close()
