"""
Lokaler Webserver fuer den Rechtsprechungs-Agenten.
Startet auf http://localhost:8765 — kein zusaetzliches Package noetig.
Alle Scraper und die Claude-API sind synchron – kein asyncio, kein Event-Loop-Problem.
"""

import io
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# .env laden (ohne externes Package)
def _load_dotenv():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

_load_dotenv()

# Windows UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from main import PORTALE, agent
from prompt_parser import parse_prompt
from summarizer import beantworte_folgefrage, erstelle_blogbeitrag

PORT = 8765
TEMPLATE = Path(__file__).parent / "templates" / "index.html"

# ── Job-Verwaltung ────────────────────────────────────────────────────────────

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def _new_job() -> str:
    jid = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[jid] = {
            "status": "pending",
            "portale": [],
            "treffer": [],
            "zusammenfassung": "",
            "fehler": [],
            "started": time.time(),
        }
    return jid


def _progress_cb(jid: str):
    def _cb(portal_name: str, status: str, treffer_count):
        with _jobs_lock:
            job = _jobs[jid]
            if portal_name == "__summary__":
                job["summary_status"] = status
                return
            for entry in job["portale"]:
                if entry["name"] == portal_name:
                    entry["status"] = status
                    if treffer_count is not None:
                        entry["treffer"] = treffer_count
                    return
            job["portale"].append({
                "name": portal_name,
                "status": status,
                "treffer": treffer_count if treffer_count is not None else 0,
            })
    return _cb


def _run_search(jid: str, params: dict):
    """Führt die Suche synchron im HTTP-Handler-Thread aus."""
    try:
        result = agent(
            suchbegriff=params["suchbegriff"],
            nur_portale=params.get("portale") or None,
            datum_von=params.get("datum_von"),
            datum_bis=params.get("datum_bis"),
            gerichtstyp=params.get("gerichtstyp"),
            anweisung=params.get("anweisung"),
            max_treffer=params.get("max_treffer", 5) or 10000,
            max_treffer_gesamt=params.get("max_treffer_gesamt") or None,
            on_progress=_progress_cb(jid),
        )
        with _jobs_lock:
            _jobs[jid]["status"] = "done"
            _jobs[jid]["treffer"] = result["treffer"]
            _jobs[jid]["zusammenfassung"] = result["zusammenfassung"]
            _jobs[jid]["fehler"] = result["fehler"]
    except Exception as e:
        with _jobs_lock:
            _jobs[jid]["status"] = "error"
            _jobs[jid]["fehler"].append({"portal": "Agent", "fehler": str(e)})


# ── HTTP-Handler ──────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # Konsole sauber halten

    def _send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _handle_index(self):
        self._send_html(TEMPLATE.read_text(encoding="utf-8"))

    def _handle_parse(self):
        body = self._read_body()
        prompt = body.get("prompt", "").strip()
        if not prompt:
            self._send_json({"error": "Kein Prompt angegeben."}, 400)
            return
        try:
            params = parse_prompt(prompt)
            self._send_json(params)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_search(self):
        params = self._read_body()
        if not params.get("suchbegriff") and not params.get("datum_von") and not params.get("datum_bis") and not params.get("anweisung"):
            self._send_json({"error": "Bitte mindestens Suchbegriff, Zeitraum oder Anweisung angeben."}, 400)
            return
        jid = _new_job()
        t = threading.Thread(target=_run_search, args=(jid, params), daemon=True)
        t.start()
        self._send_json({"job": jid})

    def _handle_status(self):
        qs = parse_qs(urlparse(self.path).query)
        jid = qs.get("job", [None])[0]
        if not jid:
            self._send_json({"error": "Kein job-Parameter."}, 400)
            return
        with _jobs_lock:
            job = _jobs.get(jid)
        if job is None:
            self._send_json({"error": "Unbekannte Job-ID."}, 404)
            return
        self._send_json(job)

    def _handle_blogpost(self):
        body = self._read_body()
        jid = body.get("job")
        if not jid:
            self._send_json({"error": "job erforderlich."}, 400)
            return
        with _jobs_lock:
            job = _jobs.get(jid)
        if not job:
            self._send_json({"error": "Unbekannte Job-ID."}, 404)
            return
        try:
            result = erstelle_blogbeitrag(
                treffer=job["treffer"],
                zusammenfassung=job["zusammenfassung"],
            )
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_followup(self):
        body = self._read_body()
        jid = body.get("job")
        frage = (body.get("frage") or "").strip()
        verlauf = body.get("verlauf") or []
        if not jid or not frage:
            self._send_json({"error": "job und frage erforderlich."}, 400)
            return
        with _jobs_lock:
            job = _jobs.get(jid)
        if not job:
            self._send_json({"error": "Unbekannte Job-ID."}, 404)
            return
        try:
            antwort = beantworte_folgefrage(
                treffer=job["treffer"],
                zusammenfassung=job["zusammenfassung"],
                frage=frage,
                verlauf=verlauf,
            )
            self._send_json({"antwort": antwort})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_portale(self):
        self._send_json([p["name"] for p in PORTALE])

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._handle_index()
        elif path == "/status":
            self._handle_status()
        elif path == "/portale":
            self._handle_portale()
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/parse":
            self._handle_parse()
        elif path == "/search":
            self._handle_search()
        elif path == "/followup":
            self._handle_followup()
        elif path == "/blogpost":
            self._handle_blogpost()
        else:
            self.send_response(404)
            self.end_headers()


# ── Start ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"\nRechtsprechungs-Agent laeuft auf http://localhost:{PORT}")
    print("Strg+C zum Beenden.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer gestoppt.")
