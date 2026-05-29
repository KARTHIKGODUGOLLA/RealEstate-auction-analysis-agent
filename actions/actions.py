"""Rasa actions that expose the auction analysis engine."""

from __future__ import annotations

from typing import Any

from auction_agent.engine import analyze_auction
from auction_agent.memory import save_analysis, update_buyer_profile
from auction_agent.report import render_report

try:
    from rasa_sdk import Action, Tracker
    from rasa_sdk.executor import CollectingDispatcher
except ImportError:  # Allows unit tests/imports without installing Rasa SDK yet.
    class Action:  # type: ignore[no-redef]
        def name(self) -> str:
            return self.__class__.__name__

    class Tracker:  # type: ignore[no-redef]
        def get_slot(self, key: str) -> Any:
            return None

    class CollectingDispatcher:  # type: ignore[no-redef]
        def utter_message(self, text: str) -> None:
            print(text)


class ActionAnalyzeAuctionProperty(Action):
    def name(self) -> str:
        return "action_analyze_auction_property"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: dict[str, Any],
    ) -> list[dict[str, Any]]:
        property_overrides = {
            "address": tracker.get_slot("property_address"),
            "city": tracker.get_slot("city"),
            "current_bid": _to_int(tracker.get_slot("current_bid")),
            "estimated_repairs": _to_int(tracker.get_slot("estimated_repairs")),
            "estimated_market_rent": _to_int(tracker.get_slot("market_rent")),
        }
        profile_overrides = {
            "available_cash": _to_int(tracker.get_slot("available_cash")),
            "financing_type": tracker.get_slot("financing_type"),
            "investment_goal": tracker.get_slot("investment_goal"),
        }

        update_buyer_profile(profile_overrides)
        analysis = analyze_auction(
            property_id="6013-fender-court",
            property_overrides=property_overrides,
            profile_overrides=profile_overrides,
        )
        save_analysis(analysis)
        dispatcher.utter_message(text=render_report(analysis))
        return []


def _to_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(float(str(value).replace(",", "").replace("$", "")))
