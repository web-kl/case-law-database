"""
Scraper für Bund (Rechtsprechung im Internet)
"""
from urllib.parse import quote
from playwright.sync_api import sync_playwright

_BASE = "https://www.rechtsprechung-im-internet.de/jportal/portal/page/bsjrsprod.psml"

def suche_bund(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    if suchbegriff:
        params = (
            "eventSubmit_doSearch=suchen"
            "&action=portlets.jw.MainAction"
            "&form=bsjrsFastSearch"
            f"&query={quote(suchbegriff)}"
            "&desc=all"
            "&formhaschangedvalue=yes"
            "&wt_form=1"
            "&deletemask=no"
        )
        if datum_von:
            params += f"&dateFrom={quote(datum_von)}"
        if datum_bis:
            params += f"&dateTo={quote(datum_bis)}"
    else:
        params = (
            "eventSubmit_doSearch=suchen"
            "&action=portlets.jw.MainAction"
            "&form=jurisExpertSearch"
            "&desc=text&query="
            f"&desc=date&query=date"
            f"&dateFrom={quote(datum_von or '')}"
            f"&dateTo={quote(datum_bis or '')}"
            "&standardsuche=suchen"
            "&deletemask=no"
            "&wt_form=1"
        )

    url = f"{_BASE}?{params}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)

            link_data = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a'))
                    .filter(a => a.innerText.includes('|') && a.innerText.length > 10
                                 && !['Kurztext','Langtext'].includes(a.innerText.trim()))
                    .map(a => {
                        var parent = a.closest('tr, li, div') || a.parentElement;
                        var parentText = parent ? parent.innerText : '';
                        var dateMatch = parentText.match(/\\d{2}\\.\\d{2}\\.\\d{4}/);
                        return {
                            text: a.innerText.trim(),
                            href: a.href,
                            datum: dateMatch ? dateMatch[0] : ''
                        };
                    });
            }""")

            treffer = []
            gesehen = set()

            for item in link_data:
                try:
                    text = item["text"]
                    href = item["href"]
                    datum_str = item["datum"]
                    if not href or href in gesehen:
                        continue
                    if not href.startswith("http"):
                        href = "https://www.rechtsprechung-im-internet.de" + href

                    gesehen.add(href)
                    zeilen = [z.strip() for z in text.split("\n") if z.strip()]
                    zeile1 = zeilen[0] if zeilen else text
                    teile1 = zeile1.split("|")
                    gericht_name = teile1[0].strip() if teile1 else ""
                    az = teile1[1].strip() if len(teile1) > 1 else ""
                    vorschau = " | ".join(zeilen[1:]) if len(zeilen) > 1 else text

                    treffer.append({
                        "titel": zeile1,
                        "url": href,
                        "gericht": gericht_name,
                        "datum": datum_str,
                        "aktenzeichen": az,
                        "vorschau": vorschau[:500],
                    })
                    if len(treffer) >= max_treffer:
                        break
                except Exception:
                    continue

            return treffer
        except Exception as e:
            raise RuntimeError(f"Bund-Suche fehlgeschlagen: {e}")
        finally:
            browser.close()
