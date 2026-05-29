"""Small no-dependency web server for the auction advisor UI."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from auction_agent.engine import analyze_auction
from auction_agent.memory import save_analysis, update_buyer_profile
from auction_agent.official_data import OFFICIAL_SOURCE_DIRECTORY
from auction_agent.prepared_data import list_prepared_properties

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web"


class AuctionAdvisorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/sources":
            body = json.dumps({"sources": OFFICIAL_SOURCE_DIRECTORY}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/properties":
            body = json.dumps({"properties": list_prepared_properties()}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in {"/", "/index.html"}:
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if self.path == "/styles.css":
            self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if self.path == "/app.js":
            self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        if self.path == "/api/rasa-chat":
            self._proxy_rasa_message()
            return
        if self.path != "/api/analyze":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        property_overrides = {
            "address": payload.get("address") or None,
            "city": payload.get("city") or None,
            "current_bid": _to_int(payload.get("currentBid")),
            "estimated_repairs": _to_int(payload.get("estimatedRepairs")),
            "estimated_market_rent": _to_int(payload.get("marketRent")),
        }
        profile_overrides = {
            "available_cash": _to_int(payload.get("availableCash")),
            "financing_type": payload.get("financingType") or None,
            "investment_goal": payload.get("investmentGoal") or None,
        }

        analysis = analyze_auction(
            property_id=payload.get("parcelId") or "6013-fender-court",
            property_overrides=property_overrides,
            profile_overrides=profile_overrides,
        )
        update_buyer_profile(profile_overrides)
        save_analysis(analysis)
        body = json.dumps(_serialize_analysis(analysis)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy_rasa_message(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        message = payload.get("message", "")
        sender = payload.get("sender", "web-demo")
        rasa_payload = json.dumps({"sender": sender, "message": message}).encode("utf-8")
        request = Request(
            "http://127.0.0.1:5005/webhooks/rest/webhook",
            data=rasa_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
        except (OSError, URLError) as exc:
            body = json.dumps(
                {
                    "error": "Rasa is not reachable. Start it with `make rasa` while `make run-actions` is running.",
                    "detail": str(exc),
                }
            ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_file(self, path: Path, content_type: str) -> None:
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), AuctionAdvisorHandler)
    print(f"Auction Advisor UI -> http://{host}:{port}")
    server.serve_forever()


def _serialize_analysis(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _serialize_analysis(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {key: _serialize_analysis(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_analysis(item) for item in value]
    return value


def _to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(float(str(value).replace(",", "")))


if __name__ == "__main__":
    run()
