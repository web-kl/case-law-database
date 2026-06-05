"""
Zusammenfassung der Suchergebnisse mit Claude.
Nutzt die Anthropic API mit claude-sonnet-4-6.
"""

import os
import anthropic


# API-Key aus Umgebungsvariable (niemals hardcoden!)
# Setzen Sie: export ANTHROPIC_API_KEY="sk-ant-..."
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


async def erstelle_zusammenfassung(
    suchbegriff: str,
    treffer: list[dict],
    anweisung: str | None = None,
) -> str:
    """
    Übergibt alle Suchergebnisse an Claude und erhält eine
    strukturierte juristische Zusammenfassung zurück.
    """

    # Treffer als Text aufbereiten
    treffer_text = _formatiere_treffer(treffer)

    # Statistik für den Prompt
    portale = sorted({t.get("portal", "?") for t in treffer})
    anzahl = len(treffer)

    anweisung_block = f"\n**Besondere Auswertungsanweisung:** {anweisung}\nRichte die gesamte Analyse und Zusammenfassung an dieser Anweisung aus.\n" if anweisung else ""

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

    # Synchroner API-Aufruf (Anthropic SDK ist nicht async-nativ)
    import asyncio
    loop = asyncio.get_event_loop()
    antwort = await loop.run_in_executor(None, _api_aufruf, prompt)

    return antwort


def _api_aufruf(prompt: str) -> str:
    """Führt den synchronen Claude API-Aufruf aus."""
    client = _get_client()

    nachricht = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    return nachricht.content[0].text


def _formatiere_treffer(treffer: list[dict]) -> str:
    """Formatiert die Treffer-Liste als lesbaren Text für den Prompt."""
    teile = []

    for i, t in enumerate(treffer, 1):
        portal   = t.get("portal", "?")
        titel    = t.get("titel", "?")
        gericht  = t.get("gericht", "")
        datum    = t.get("datum", "")
        az       = t.get("aktenzeichen", "")
        vorschau = t.get("vorschau", "")[:400]  # Auf 400 Zeichen begrenzen
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
