"""Small no-dependency web server for the auction advisor UI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
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
RASA_REPLY_TIMEOUT_SECONDS = 4
SPEECH_PROCESS: subprocess.Popen[bytes] | None = None


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
        if self.path == "/api/speak":
            self._speak_locally()
            return
        if self.path == "/api/tts":
            self._generate_tts_audio()
            return
        if self.path == "/api/stop-speech":
            self._stop_local_speech()
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
            use_official_data=_wants_live_official_data(payload),
        )
        update_buyer_profile(profile_overrides)
        save_analysis(analysis)
        body = json.dumps(_serialize_analysis(analysis)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _speak_locally(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = _speech_text(payload.get("text", ""))
        if not text:
            self._send_json({"ok": False, "error": "No text to speak."})
            return

        say_path = shutil.which("say")
        if not say_path:
            self._send_json({"ok": False, "error": "System voice is unavailable on this machine."})
            return

        global SPEECH_PROCESS
        _stop_speech_process()
        SPEECH_PROCESS = subprocess.Popen(
            [say_path, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._send_json({"ok": True, "engine": "macos-say"})

    def _generate_tts_audio(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = _speech_text(payload.get("text", ""))
        if not text:
            self._send_json({"ok": False, "error": "No text to speak."}, status=400)
            return

        say_path = shutil.which("say")
        if not say_path:
            self._send_json({"ok": False, "error": "macOS say is unavailable."}, status=503)
            return

        fd, audio_path = tempfile.mkstemp(suffix=".m4a")
        os.close(fd)
        try:
            subprocess.run(
                [
                    say_path,
                    "-o",
                    audio_path,
                    "--file-format=m4af",
                    "--data-format=aac",
                    text,
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=20,
            )
            body = Path(audio_path).read_bytes()
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            self._send_json({"ok": False, "error": f"Could not generate speech audio: {exc}"}, status=500)
            return
        finally:
            Path(audio_path).unlink(missing_ok=True)

        self.send_response(200)
        self.send_header("Content-Type", "audio/mp4")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stop_local_speech(self) -> None:
        _stop_speech_process()
        self._send_json({"ok": True})

    def _proxy_rasa_message(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        message = payload.get("message", "")
        sender = payload.get("sender", "web-demo")
        fallback = _local_advisor_reply(message, payload.get("context", {}))
        if _should_use_demo_answer(message):
            body = json.dumps([fallback]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        rasa_payload = json.dumps({"sender": sender, "message": message}).encode("utf-8")
        request = Request(
            "http://127.0.0.1:5005/webhooks/rest/webhook",
            data=rasa_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=RASA_REPLY_TIMEOUT_SECONDS) as response:
                body = response.read()
        except (OSError, URLError) as exc:
            fallback["rasa_status"] = f"Rasa was not reachable: {exc}"
            body = json.dumps([fallback]).encode("utf-8")
        else:
            try:
                messages = json.loads(body or b"[]")
            except json.JSONDecodeError:
                fallback["rasa_status"] = "Rasa returned a response the web demo could not parse."
                body = json.dumps([fallback]).encode("utf-8")
            else:
                texts = [item.get("text", "") for item in messages if isinstance(item, dict)]
                has_text = any(texts)
                if (
                    not has_text
                    or _is_collection_prompt(texts)
                    or _is_unhelpful_rasa_answer(texts)
                    or _is_too_long_for_voice(texts)
                ):
                    fallback["rasa_status"] = (
                        "Rasa returned no speakable answer."
                        if not has_text
                        else "Rasa did not use the dashboard analysis context."
                    )
                    body = json.dumps([fallback]).encode("utf-8")

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

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
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


def _speech_text(value: Any) -> str:
    return " ".join(str(value).split()).replace("$", " dollars ").replace("%", " percent ")[:420]


def _stop_speech_process() -> None:
    global SPEECH_PROCESS
    if SPEECH_PROCESS and SPEECH_PROCESS.poll() is None:
        SPEECH_PROCESS.terminate()
    SPEECH_PROCESS = None


def _local_advisor_reply(message: str, context: dict[str, Any] | None) -> dict[str, str]:
    """Deterministic chat fallback for demo mode when Rasa is down or quiet."""
    context = context or {}
    property_overrides = {
        "address": context.get("address") or None,
        "city": context.get("city") or None,
        "current_bid": _to_int(context.get("currentBid")),
        "estimated_repairs": _to_int(context.get("estimatedRepairs")),
        "estimated_market_rent": _to_int(context.get("marketRent")),
    }
    profile_overrides = {
        "available_cash": _to_int(context.get("availableCash")),
        "financing_type": context.get("financingType") or None,
        "investment_goal": context.get("investmentGoal") or None,
    }
    analysis = analyze_auction(
        property_id=context.get("parcelId") or "6013-fender-court",
        property_overrides=property_overrides,
        profile_overrides=profile_overrides,
        use_official_data=_wants_live_official_data(context),
    )
    update_buyer_profile(profile_overrides)
    save_analysis(analysis)

    prompt = message.lower()
    rec = analysis.recommendation
    buying = analysis.buying_power
    hidden = analysis.hidden_costs
    rental = analysis.rental_yield
    prop = analysis.property_data

    if any(term in prompt for term in ("max", "maximum", "safe bid", "bid above")):
        if rec.max_safe_bid <= 0:
            answer = (
                "Bid call: pass at this price. "
                f"The current bid needs about {_money(buying.cash_needed_at_current_bid)} cash, "
                f"which leaves {_money(buying.remaining_cash_at_current_bid)} after reserves. "
                "That is too tight for this buyer profile."
            )
        else:
            answer = (
                f"Max safe bid: {_money(rec.max_safe_bid)}. "
                f"Do not bid above {_money(rec.do_not_bid_above)}. "
                f"The current bid needs about {_money(buying.cash_needed_at_current_bid)} cash, "
                f"which leaves {_money(buying.remaining_cash_at_current_bid)}; that is too tight for this profile."
            )
    elif any(term in prompt for term in ("wrong", "risk", "risks", "cost", "lien", "title")):
        top_risks = [
            item["source"]
            for item in hidden.checklist
            if item["risk_level"] == "high" and item["status"] in {"risk_found", "needs_review", "not_checked"}
        ][:3]
        risk_list = ", ".join(top_risks) if top_risks else "taxes, title, and code records"
        answer = (
            f"Main risk: {rec.biggest_risk}. "
            f"Check {risk_list} before bidding. "
            f"My recommendation stays {rec.category.lower()} until those records are clean."
        )
    else:
        decision = "Pass for now" if rec.category == "Red light" else "Proceed only with verification"
        answer = (
            f"{decision}. {rec.category}; max safe bid {_money(rec.max_safe_bid)}. "
            f"Projected cash flow is {_money(rental.monthly_cash_flow)} per month, "
            f"and the key blocker is {rec.biggest_risk}."
        )

    return {"text": answer, "source": "local-demo-fallback"}


def _wants_live_official_data(payload: dict[str, Any]) -> bool:
    return str(payload.get("useOfficialData", "")).lower() in {"1", "true", "yes", "on"}


def _money(value: int | float) -> str:
    prefix = "-$" if value < 0 else "$"
    return f"{prefix}{abs(value):,.0f}"


def _is_collection_prompt(texts: list[str]) -> bool:
    collection_phrases = (
        "what repair budget",
        "what monthly rent",
        "what is the current bid",
        "how much cash",
        "how would you finance",
        "what property address",
        "what city or county",
        "are you evaluating this",
    )
    combined = " ".join(texts).lower()
    return any(phrase in combined for phrase in collection_phrases)


def _is_unhelpful_rasa_answer(texts: list[str]) -> bool:
    combined = " ".join(texts).lower()
    unhelpful_phrases = (
        "can't determine",
        "can't calculate",
        "cannot determine",
        "cannot calculate",
        "don't have access",
        "don't have enough",
        "do not have enough",
        "needed to figure out",
        "provide a repair budget",
    )
    return any(phrase in combined for phrase in unhelpful_phrases)


def _is_too_long_for_voice(texts: list[str]) -> bool:
    return len(" ".join(texts)) > 900


def _should_use_demo_answer(message: str) -> bool:
    prompt = message.lower()
    demo_terms = (
        "should i bid",
        "maximum safe bid",
        "max bid",
        "bid above",
        "what could go wrong",
        "risk",
        "risks",
        "selected property",
        "auction property",
    )
    return any(term in prompt for term in demo_terms)


if __name__ == "__main__":
    run()
