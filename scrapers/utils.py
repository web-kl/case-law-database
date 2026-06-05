import re
from datetime import datetime, timezone

def parse_titel(titel):
    meta = {}
    d = re.search(r'\d{1,2}\.\d{1,2}\.\d{4}', titel)
    meta['datum'] = d.group() if d else ""
    az = re.search(r'[–-]\s*([A-Z0-9][\w\s./]+\d{2,})', titel)
    if az: meta['aktenzeichen'] = az.group(1).strip()
    else:
        az2 = re.search(r'\b(\d+\s*\w+\s*\d+/\d+)\b', titel)
        meta['aktenzeichen'] = az2.group() if az2 else ""
    meta['gericht'] = re.split(r',|v\.', titel)[0].strip()
    meta['vorschau'] = titel
    return meta


async def suche_juris3(page, portal_id, api_base, suchbegriff, max_treffer, datum_von, datum_bis):
    """
    Generische Suchfunktion für juris3-Portale (landesrecht-*.de).
    Ruft die REST-API auf, nachdem ein CSRF-Token von der Suchseite geholt wurde.
    """
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

    csrf = None
    def _grab(r):
        nonlocal csrf
        if "x-csrf-token" in r.headers:
            csrf = r.headers["x-csrf-token"]
    page.on("request", _grab)

    search_url = f"{api_base}/{portal_id}/search"
    await page.goto(search_url, wait_until="networkidle", timeout=60000)
    await page.wait_for_timeout(3000)

    # Fallback: CSRF-Token aus localStorage lesen (z.B. Hamburg)
    if not csrf:
        csrf = await page.evaluate("""() => {
            try {
                var raw = localStorage.getItem('r3Tab_gcData');
                if (raw) return JSON.parse(raw).token || null;
            } catch(e) {}
            return null;
        }""")

    searches = []
    if suchbegriff:
        searches.append({"id": "Text", "value": suchbegriff})
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
                "size": max_treffer,
                "sort": "juris",
                "addToHistory": True,
                "addCategory": True,
            },
            "SEARCH_WORD_HITS": {},
        },
        "filters": {"CATEGORY": ["Alles"]},
        "searches": searches,
        "clientID": portal_id,
        "clientVersion": f"{portal_id} - V08_30_01 - 01.01.2026 00:00",
        "r3ID": r3id,
    }

    api_url = f"{api_base}/jportal/wsrest/recherche3/search"
    data = await page.evaluate(_JS_FETCH, [api_url, payload, csrf])
    if "error" in data:
        raise RuntimeError(f"API {data['error']}: {data.get('body', '')[:200]}")

    treffer = []
    for doc in data.get("resultList", []):
        if doc.get("categoryId") != "Rechtsprechung":
            continue
        titles = doc.get("titleList", [])
        subs   = doc.get("subtitleList", [])
        doc_id = doc.get("docId", "")
        treffer.append({
            "titel":        f"{titles[0] if titles else ''}: {titles[1] if len(titles) > 1 else ''}".strip(": "),
            "url":          f"{api_base}/{portal_id}/document/{doc_id}" if doc_id else "",
            "gericht":      titles[0] if titles else "",
            "datum":        doc.get("date", ""),
            "aktenzeichen": titles[1] if len(titles) > 1 else "",
            "vorschau":     f"{subs[0] if subs else ''} | {subs[1] if len(subs) > 1 else ''}"[:500],
        })
        if len(treffer) >= max_treffer:
            break
    return treffer
