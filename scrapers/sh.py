from datetime import datetime, timezone
from playwright.async_api import async_playwright

_BASE = "https://www.gesetze-rechtsprechung.sh.juris.de"
_PORTAL_ID = "bssh"

_JS_FETCH = """
    async ([url, payload, csrf]) => {
        const resp = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'juris-portalid': payload.clientID,
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

_JS_FIND_CSRF = """() => {
    // 1. Alle localStorage-Keys durchsuchen
    for (var i = 0; i < localStorage.length; i++) {
        var key = localStorage.key(i);
        try {
            var val = JSON.parse(localStorage.getItem(key));
            if (val && val.token) return val.token;
            if (val && val.csrfToken) return val.csrfToken;
            if (val && val['x-csrf-token']) return val['x-csrf-token'];
        } catch(e) {}
    }
    // 2. sessionStorage
    for (var i = 0; i < sessionStorage.length; i++) {
        var key = sessionStorage.key(i);
        try {
            var val = JSON.parse(sessionStorage.getItem(key));
            if (val && val.token) return val.token;
            if (val && val.csrfToken) return val.csrfToken;
        } catch(e) {}
    }
    // 3. Meta-Tag
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    return null;
}"""

async def suche_sh(suchbegriff, max_treffer=5, datum_von=None, datum_bis=None, gericht=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()
        try:
            csrf = None

            # CSRF aus Request-Headers abfangen
            def _grab_request(r):
                nonlocal csrf
                v = r.headers.get("x-csrf-token")
                if v:
                    csrf = v

            # CSRF aus Response-Headers abfangen
            def _grab_response(r):
                nonlocal csrf
                v = r.headers.get("x-csrf-token")
                if v:
                    csrf = v

            page.on("request", _grab_request)
            page.on("response", _grab_response)

            # Seite laden und länger warten damit JS vollständig initialisiert
            await page.goto(f"{_BASE}/{_PORTAL_ID}/search",
                            wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(5000)

            # Fallback: Storage und Meta-Tags durchsuchen
            if not csrf:
                csrf = await page.evaluate(_JS_FIND_CSRF)

            # Letzter Fallback: Suche im Seitenquelltext
            if not csrf:
                content = await page.content()
                import re
                m = re.search(r'"token"\s*:\s*"([^"]{10,})"', content)
                if m:
                    csrf = m.group(1)

            if not csrf:
                raise RuntimeError("CSRF-Token nicht gefunden")

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
                "clientID": _PORTAL_ID,
                "clientVersion": f"{_PORTAL_ID} - V08_30_01 - 01.01.2026 00:00",
                "r3ID": r3id,
            }

            api_url = f"{_BASE}/jportal/wsrest/recherche3/search"
            data = await page.evaluate(_JS_FETCH, [api_url, payload, csrf])
            if "error" in data:
                raise RuntimeError(f"API {data['error']}: {data.get('body', '')[:300]}")

            treffer = []
            for doc in data.get("resultList", []):
                if doc.get("categoryId") != "Rechtsprechung":
                    continue
                titles = doc.get("titleList", [])
                subs   = doc.get("subtitleList", [])
                doc_id = doc.get("docId", "")
                treffer.append({
                    "titel":        f"{titles[0] if titles else ''}: {titles[1] if len(titles) > 1 else ''}".strip(": "),
                    "url":          f"{_BASE}/{_PORTAL_ID}/document/{doc_id}" if doc_id else "",
                    "gericht":      titles[0] if titles else "",
                    "datum":        doc.get("date", ""),
                    "aktenzeichen": titles[1] if len(titles) > 1 else "",
                    "vorschau":     f"{subs[0] if subs else ''} | {subs[1] if len(subs) > 1 else ''}"[:500],
                })
                if len(treffer) >= max_treffer:
                    break
            return treffer

        except Exception as e:
            raise RuntimeError(f"SH-Suche fehlgeschlagen: {e}")
        finally:
            await browser.close()
