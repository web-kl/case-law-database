"""
Zusammenfassung der Suchergebnisse mit Claude.
Nutzt die Anthropic API mit claude-sonnet-4-6.
Alle Funktionen sind synchron – kein asyncio, kein Event-Loop-Problem.
"""

import os
import anthropic


_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY nicht gesetzt.\n"
                "Bitte ausführen: export ANTHROPIC_API_KEY='sk-ant-...'"
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def erstelle_zusammenfassung(
    suchbegriff: str,
    treffer: list[dict],
    anweisung: str | None = None,
) -> str:
    """
    Übergibt alle Suchergebnisse an Claude und erhält eine
    strukturierte juristische Zusammenfassung zurück.
    """
    treffer_text = _formatiere_treffer(treffer)
    portale = sorted({t.get("portal", "?") for t in treffer})
    anzahl = len(treffer)

    anweisung_block = (
        f"\n**Besondere Auswertungsanweisung:** {anweisung}\n"
        "Richte die gesamte Analyse und Zusammenfassung an dieser Anweisung aus.\n"
    ) if anweisung else ""

    prompt = f"""Du bist ein juristischer Assistent. Analysiere die folgenden Suchergebnisse aus deutschen Landesrechtsdatenbanken und erstelle eine strukturierte juristische Zusammenfassung.

**Suchbegriff:** {suchbegriff}
**Datenbanken:** {', '.join(portale)}
**Gefundene Entscheidungen:** {anzahl}
{anweisung_block}
---

{treffer_text}

---

Erstelle eine Zusammenfassung mit folgender Struktur:

## 1. Überblick
Kurze Übersicht: Wie viele Treffer, welche Gerichte, welcher Zeitraum.

## 2. Rechtliche Kernfragen
Welche Rechtsfragen und Rechtsnormen werden behandelt?

## 3. Wesentliche Aussagen der Entscheidungen
Für jede relevante Entscheidung:
- **Gericht, Datum, Aktenzeichen**
- Kernaussage in 2–3 Sätzen

## 4. Tendenzen und Entwicklungen
Gibt es erkennbare Rechtsprechungslinien oder abweichende Entscheidungen?

## 5. Hinweis
Kurzer Hinweis auf Vollständigkeit und Empfehlung zur Vertiefung.

Bleibe dabei strikt bei den übergebenen Informationen. Erfinde keine Aktenzeichen, Daten oder Inhalte."""

    return _api_aufruf(prompt)


def _api_aufruf(prompt: str) -> str:
    """Führt den synchronen Claude API-Aufruf aus."""
    client = _get_client()
    nachricht = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return nachricht.content[0].text


_BLOGBEITRAG_TOOL = {
    "name": "blogbeitrag_ausgeben",
    "description": "Gibt den fertigen Blogbeitrag strukturiert aus.",
    "input_schema": {
        "type": "object",
        "properties": {
            "titel": {
                "type": "string",
                "description": "Prägnanter, neugierig machender Titel, max. 70 Zeichen.",
            },
            "blogbeitrag": {
                "type": "string",
                "description": (
                    "Fertiger Blogbeitrag als Markdown. Struktur: kurze Einleitung "
                    "(2-3 Sätze), Hauptteil mit den wichtigsten Entscheidungen in "
                    "Alltagssprache ohne Juristenjargon, kurzes Fazit. 300-500 Wörter."
                ),
            },
            "meta": {
                "type": "string",
                "description": "Meta-Beschreibung für Suchmaschinen, max. 160 Zeichen.",
            },
        },
        "required": ["titel", "blogbeitrag", "meta"],
    },
}


def _api_aufruf_blog(prompt: str) -> dict:
    client = _get_client()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        tools=[_BLOGBEITRAG_TOOL],
        tool_choice={"type": "tool", "name": "blogbeitrag_ausgeben"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "blogbeitrag_ausgeben":
            return block.input
    return {"titel": "", "blogbeitrag": "", "meta": ""}


def erstelle_blogbeitrag(
    treffer: list[dict],
    zusammenfassung: str,
) -> dict:
    """Erstellt einen fertigen Blogbeitrag mit Titel, Text und Meta-Beschreibung."""
    treffer_text = _formatiere_treffer(treffer)

    prompt = f"""Du bist Redakteur eines populären Rechtsblogs für die breite Öffentlichkeit. Erstelle basierend auf der folgenden Recherche einen fertigen Blogbeitrag.

ZUSAMMENFASSUNG DER RECHERCHE:
{zusammenfassung}

GEFUNDENE ENTSCHEIDUNGEN:
{treffer_text}

Schreibe für juristische Laien. Erkläre, was die Entscheidungen für den Alltag der Leser bedeuten."""

    return _api_aufruf_blog(prompt)


def beantworte_folgefrage(
    treffer: list[dict],
    zusammenfassung: str,
    frage: str,
    verlauf: list[dict] | None = None,
) -> str:
    """Beantwortet eine Folgefrage zu den bereits gefundenen Ergebnissen."""
    treffer_text = _formatiere_treffer(treffer)

    verlauf_block = ""
    if verlauf:
        for v in verlauf:
            verlauf_block += f"\nFrage: {v['frage']}\nAntwort: {v['antwort']}\n"
        verlauf_block = "\n\nBisheriger Gesprächsverlauf:\n" + verlauf_block

    prompt = f"""Du bist ein juristischer Assistent. Der Nutzer hat eine Recherche in deutschen Rechtsprechungsdatenbanken durchgeführt und stellt nun eine Folgefrage zu den Ergebnissen.

ZUSAMMENFASSUNG DER RECHERCHE:
{zusammenfassung}

GEFUNDENE ENTSCHEIDUNGEN:
{treffer_text}
{verlauf_block}

AKTUELLE FRAGE:
{frage}

Beantworte die Frage präzise und basierend auf den vorliegenden Ergebnissen. Zitiere relevante Entscheidungen mit Gericht und Aktenzeichen, wo sinnvoll. Wenn die Frage nicht aus den Ergebnissen beantwortet werden kann, weise klar darauf hin."""

    return _api_aufruf(prompt)


def _formatiere_treffer(treffer: list[dict]) -> str:
    """Formatiert die Treffer-Liste als lesbaren Text für den Prompt."""
    teile = []

    for i, t in enumerate(treffer, 1):
        portal   = t.get("portal", "?")
        titel    = t.get("titel", "?")
        gericht  = t.get("gericht", "")
        datum    = t.get("datum", "")
        az       = t.get("aktenzeichen", "")
        vorschau = t.get("vorschau", "")[:400]
        url      = t.get("url", "")

        teil = f"**Treffer {i}** [{portal}]\n"
        if gericht: teil += f"Gericht: {gericht}\n"
        if datum:   teil += f"Datum: {datum}\n"
        if az:      teil += f"Aktenzeichen: {az}\n"
        teil += f"Titel: {titel}\n"
        if vorschau and vorschau != titel:
            teil += f"Vorschau: {vorschau}\n"
        if url:     teil += f"URL: {url}\n"

        teile.append(teil)

    return "\n---\n".join(teile)
