"""
Scraper für Sachsen – 2 Portale:
  1. esamosplus  – OLG Dresden + weitere Gerichte
     https://www.justiz.sachsen.de/esamosplus/pages/index.aspx
     Datum-Filter möglich; Volltext-Checkbox vorhanden.
  2. OVG Sachsen – Oberverwaltungsgericht
     https://www.justiz.sachsen.de/ovgentschweb/
     Kein Datum-Filter; keine Volltext-Checkbox.
"""
import re
from playwright.sync_api import sync_playwright

_BASE_ESAMOS = "https://www.justiz.sachsen.de/esamosplus/pages/index.aspx"
_BASE_OVG    = "https://www.justiz.sachsen.de/ovgentschweb/"


def _suche_esamos(page, suchbegriff: str, max_treffer: int,
                   datum_von=None, datum_bis=None) -> list[dict]:
    treffer = []
    try:
        page.goto(_BASE_ESAMOS, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)

        frame = next((f for f in page.frames if "suchen.aspx" in f.url), None)
        if not frame:
            raise RuntimeError("esamosplus: suchen.aspx frame nicht gefunden")

        frame.evaluate("""(args) => {
            var cb = document.querySelector(
                'input[type="checkbox"][id*="volltext"], ' +
                'input[type="checkbox"][id*="Volltext"], ' +
                'input[type="checkbox"][name*="volltext"], ' +
                'input[type="checkbox"][id*="C7"]'
            );
            if (cb && !cb.checked) cb.click();

            var ta = document.querySelector('#DV13_C8');
            if (ta) { ta.readOnly = false; ta.value = args[0]; }

            var d1 = document.querySelector('#DV1_C34');
            var d2 = document.querySelector('#DV1_C35');
            if (d1 && args[1]) d1.value = args[1];
            if (d2 && args[2]) d2.value = args[2];
        }""", [suchbegriff or "", datum_von or "", datum_bis or ""])

        frame.click("#DV1_C24", force=True)
        page.wait_for_timeout(6000)

        frame2 = next((f for f in page.frames if "suchen.aspx" in f.url), None)
        if not frame2:
            raise RuntimeError("esamosplus: frame nach Suche nicht gefunden")

        rows_data = frame2.evaluate("""() => {
            var rows = Array.from(document.querySelectorAll('input[id*="DV13_Table_ctl"]'));
            var grouped = {};
            rows.forEach(el => {
                var m = el.id.match(/DV13_Table_ctl(\\d+)_DV13_Table_Col(\\d+)_C1/);
                if (m) {
                    var row = m[1], col = m[2];
                    if (!grouped[row]) grouped[row] = {};
                    grouped[row][col] = el.value;
                }
            });
            return grouped;
        }""")

        leitsatz_initial = frame2.evaluate("""() => {
            var txt = document.body.innerText;
            var idx = txt.indexOf('Selektierte Entscheidung');
            if (idx < 0) return '';
            var after = txt.substring(idx + 24).trim();
            var end   = after.indexOf('Suchergebnisse');
            return end > 0 ? after.substring(0, end).trim() : after.substring(0, 300).trim();
        }""")

        for i, (row_key, cols) in enumerate(list(rows_data.items())[:max_treffer]):
            datum        = cols.get("0", "")
            az           = cols.get("1", "")
            gericht_name = cols.get("2", "Oberlandesgericht Dresden")
            vorschau     = leitsatz_initial if i == 0 and leitsatz_initial else f"{az} vom {datum}"
            treffer.append({
                "titel":        f"{gericht_name}: {az} vom {datum}",
                "url":          _BASE_ESAMOS,
                "gericht":      gericht_name,
                "datum":        datum,
                "aktenzeichen": az,
                "vorschau":     vorschau[:500],
            })
    except Exception as e:
        print(f"    [Sachsen/esamosplus] Fehler: {e}")

    return treffer


def _suche_ovg(page, suchbegriff: str, max_treffer: int) -> list[dict]:
    treffer = []
    try:
        page.goto(_BASE_OVG, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        eingabe_gesetzt = False
        for sel in [
            "input[name='suche']", "input[name='search']", "input[name='q']",
            "input[name='volltext']", "input[type='text']", "input[type='search']",
            "textarea",
        ]:
            try:
                el = page.locator(sel).first
                if el.count() > 0:
                    el.fill(suchbegriff)
                    eingabe_gesetzt = True
                    break
            except Exception:
                continue

        if not eingabe_gesetzt:
            raise RuntimeError("OVG: Kein Suchfeld gefunden")

        abgeschickt = False
        for sel in [
            "button[type='submit']", "input[type='submit']",
            "button:has-text('Suchen')", "input[value='Suchen']",
        ]:
            try:
                btn = page.locator(sel).first
                if btn.count() > 0:
                    btn.click()
                    abgeschickt = True
                    break
            except Exception:
                continue
        if not abgeschickt:
            page.keyboard.press("Enter")

        page.wait_for_timeout(3000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        links = page.query_selector_all("a")
        gesehen: set[str] = set()

        for link in links:
            if len(treffer) >= max_treffer:
                break
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                if not href or href in gesehen or len(text) < 5:
                    continue
                if not href.startswith("http"):
                    href = "https://www.justiz.sachsen.de" + (
                        href if href.startswith("/") else "/" + href
                    )
                if "justiz.sachsen.de" not in href:
                    continue

                ist_entscheidung = (
                    re.search(r"\d+\s+[A-Za-z]", text)
                    or re.search(r"\d{2}\.\d{2}\.\d{4}", text)
                    or re.search(r"/\d{4}/", href)
                    or re.search(r"urteil|beschluss|entscheid", href, re.IGNORECASE)
                )
                if not ist_entscheidung:
                    continue

                gesehen.add(href)
                datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                az_m    = re.search(r"\b(\d+\s+[A-Za-z]+\s+\d+/\d+)", text)
                treffer.append({
                    "titel":        text[:200],
                    "url":          href,
                    "gericht":      "Oberverwaltungsgericht Sachsen",
                    "datum":        datum_m.group(1) if datum_m else "",
                    "aktenzeichen": az_m.group(1) if az_m else "",
                    "vorschau":     text[:500],
                })
            except Exception:
                continue

        if not treffer:
            for sel in [".result a", ".search-result a", "article a", "table td a", "ul li a"]:
                try:
                    elems = page.query_selector_all(sel)
                    for el in elems[:max_treffer]:
                        text = el.inner_text().strip()
                        href = el.get_attribute("href") or ""
                        if not href or len(text) < 5 or href in gesehen:
                            continue
                        if not href.startswith("http"):
                            href = "https://www.justiz.sachsen.de" + (
                                href if href.startswith("/") else "/" + href
                            )
                        gesehen.add(href)
                        datum_m = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
                        treffer.append({
                            "titel":        text[:200],
                            "url":          href,
                            "gericht":      "Oberverwaltungsgericht Sachsen",
                            "datum":        datum_m.group(1) if datum_m else "",
                            "aktenzeichen": "",
                            "vorschau":     text[:500],
                        })
                    if treffer:
                        break
                except Exception:
                    continue

    except Exception as e:
        print(f"    [Sachsen/OVG] Fehler: {e}")

    return treffer


def suche_sachsen(
    suchbegriff,
    max_treffer=10,
    datum_von=None,
    datum_bis=None,
    gericht=None,
):
    """Durchsucht esamosplus (OLG) und OVG Sachsen."""
    alle_treffer: list[dict] = []
    pro_portal = max(1, max_treffer)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page1 = browser.new_page()
            try:
                alle_treffer.extend(_suche_esamos(page1, suchbegriff, pro_portal, datum_von, datum_bis))
            finally:
                page1.close()

            page2 = browser.new_page()
            try:
                alle_treffer.extend(_suche_ovg(page2, suchbegriff, pro_portal))
            finally:
                page2.close()
        finally:
            browser.close()

    return alle_treffer
