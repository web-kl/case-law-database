from datetime import datetime, timezone
from playwright.async_api import async_playwright

API_URL = "https://www.landesrecht-bw.de/jportal/wsrest/recherche3/search"

_JS_FETCH = """
    async ([url, payload, csrf]) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'juris-portalid': 'bsbw',
                'Accept': '*/*',
                'x-csrf-token': csrf,
            },
            body: JSON.stringify(payload),
            credentials: 'include',
        });
        if (!resp.ok) return {error: resp.status, body: await resp.text()};
        return await resp.json();
    }
"""

async def suche_bw(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        try:
            csrf = None
            def _grab(r):
                nonlocal csrf
                if "x-csrf-token" in r.headers:
                    csrf = r.headers["x-csrf-token"]
            page.on("request", _grab)

            await page.goto("https://www.landesrecht-bw.de/bsbw/search",
                            wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            searches = [{"id": "Text", "value": suchbegriff or ""}]
            if datum_von or datum_bis:
                von = datum_von or "01.01.2000"
                bis = datum_bis or datetime.now().strftime("%d.%m.%Y")
                searches.append({"id": "Datum", "value": f"{von} bis {bis}"})

            now = datetime.now(timezone.utc)
            r3id = now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

            payload = {
                "searchTasks": {
                    "CATEGORY_HITS": {},
                    "RESULT_LIST": {
                        "start": 1,
                        "size": min(max_treffer, 100),
                        "sort": "juris",
                        "addToHistory": True,
                        "addCategory": True,
                    },
                    "SEARCH_WORD_HITS": {},
                },
                "filters": {"CATEGORY": ["Alles"]},
                "searches": searches,
                "clientID": "bsbw",
                "clientVersion": "bsbw - V08_30_01 - 15.05.2026 11:17",
                "r3ID": r3id,
            }

            data = await page.evaluate(_JS_FETCH, [API_URL, payload, csrf])
            if "error" in data:
                raise RuntimeError(f"BW API {data['error']}: {data.get('body', '')[:200]}")

            treffer = []
            for doc in data.get("resultList", []):
                if doc.get("categoryId") != "Rechtsprechung":
                    continue
                titles = doc.get("titleList", [])
                subs   = doc.get("subtitleList", [])
                doc_id = doc.get("docId", "")
                treffer.append({
                    "titel":        f"{titles[0] if titles else ''}: {titles[1] if len(titles) > 1 else ''}".strip(": "),
                    "url":          f"https://www.landesrecht-bw.de/bsbw/document/{doc_id}" if doc_id else "",
                    "gericht":      titles[0] if titles else "",
                    "datum":        doc.get("date", ""),
                    "aktenzeichen": titles[1] if len(titles) > 1 else "",
                    "vorschau":     f"{subs[0] if subs else ''} | {subs[1] if len(subs) > 1 else ''}"[:500],
                })
                if len(treffer) >= max_treffer:
                    break
            return treffer
        except Exception as e:
            raise RuntimeError(f"BW-Suche fehlgeschlagen: {e}")
        finally:
            await browser.close()
