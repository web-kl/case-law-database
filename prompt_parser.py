"""
Extrahiert Suchparameter aus einem natürlichsprachlichen Prompt via Claude.
"""

import json
import os
import anthropic
from datetime import datetime

_PORTAL_NAMEN = [
    "Bund", "Brandenburg", "NRW", "Bayern", "Niedersachsen",
    "Baden-Wuerttemberg", "Berlin", "Bremen", "Hamburg", "Hessen",
    "Mecklenburg-Vorpommern", "Rheinland-Pfalz", "Saarland", "Sachsen",
    "Sachsen-Anhalt", "Schleswig-Holstein", "Thueringen",
]

_SYSTEM = f"""Du extrahierst aus juristischen Suchanfragen strukturierte Parameter.
Heute ist der {datetime.now().strftime('%d.%m.%Y')}.

Verfügbare Portale: {', '.join(_PORTAL_NAMEN)}

Antworte NUR mit einem JSON-Objekt (kein Markdown, keine Erklärungen):
{{
  "suchbegriff": "Die relevanten juristischen Begriffe für die Datenbanksuche (max. 5 Wörter)",
  "datum_von": "TT.MM.JJJJ oder null",
  "datum_bis": "TT.MM.JJJJ oder null",
  "portale": ["Liste", "der", "Portale"] oder [] für alle,
  "gerichtstyp": "z.B. BGH, OLG, LG, AG, VG, LAG, SG oder leer",
  "anweisung": "Besondere Auswertungsanweisung für die Zusammenfassung, oder null"
}}

Regeln:
- "aus 2024" → datum_von: 01.01.2024, datum_bis: 31.12.2024
- "seit 2020" → datum_von: 01.01.2020, datum_bis: null
- "letzte 2 Jahre" → datum_von entsprechend berechnen, datum_bis: heute
- "BGH-Urteile" → gerichtstyp: BGH, portale: ["Bund"]
- "in Bayern" → portale: ["Bayern"]
- Keine Bundesland-Erwähnung → portale: []
- "bundesweit" oder "deutschlandweit" → portale: []

Suchbegriff-Regeln (sehr wichtig!):
- suchbegriff ist NUR für juristische Fachbegriffe und Rechtsthemen (z.B. "Mietvertrag Kündigung", "Schadensersatz Unfall")
- Bewertungskriterien wie "spektakulär", "wichtig", "interessant", "bedeutend" sind KEINE Suchbegriffe → suchbegriff: null
- "alle Urteile", "alle Entscheidungen", "neueste Urteile" → suchbegriff: null
- Wenn kein konkretes Rechtsthema genannt wird → suchbegriff: null
- Diese Kriterien gehören in die anweisung, nicht in den suchbegriff"""


def parse_prompt(prompt: str) -> dict:
    """
    Analysiert einen natürlichsprachlichen Prompt und gibt strukturierte
    Suchparameter zurück.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY nicht gesetzt.")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()
    # JSON aus der Antwort extrahieren (falls Markdown-Wrapper vorhanden)
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: Prompt als Suchbegriff verwenden
        data = {
            "suchbegriff": prompt[:100],
            "datum_von": None,
            "datum_bis": None,
            "portale": [],
            "gerichtstyp": "",
        }

    # Fehlende Felder mit Defaults füllen
    data.setdefault("suchbegriff", "")
    data.setdefault("datum_von", None)
    data.setdefault("datum_bis", None)
    data.setdefault("portale", [])
    data.setdefault("gerichtstyp", "")
    data.setdefault("anweisung", None)

    # Portale gegen bekannte Namen validieren
    if data["portale"]:
        data["portale"] = [p for p in data["portale"] if p in _PORTAL_NAMEN]

    return data
