"""Orchestrates the four widgets into one auction analysis."""

from __future__ import annotations

from dataclasses import dataclass

from auction_agent.data import BUYER_PROFILE, PROPERTIES
from auction_agent.widgets import (
    BuyingPowerResult,
    HiddenCostsResult,
    RecommendationResult,
    RentalYieldResult,
    analyze_buying_power,
    analyze_hidden_costs,
    analyze_rental_yield,
    make_recommendation,
)


@dataclass(frozen=True)
class AuctionAnalysis:
    property_data: dict
    buyer_profile: dict
    buying_power: BuyingPowerResult
    hidden_costs: HiddenCostsResult
    rental_yield: RentalYieldResult
    recommendation: RecommendationResult


def analyze_auction(property_id: str = "6013-fender-court") -> AuctionAnalysis:
    """Run the full analysis for a seeded property id."""
    property_data = PROPERTIES[property_id]
    profile = BUYER_PROFILE

    buying_power = analyze_buying_power(property_data, profile)
    rental_yield = analyze_rental_yield(property_data, purchase_price=property_data["current_bid"])
    hidden_costs = analyze_hidden_costs(property_data)
    recommendation = make_recommendation(buying_power, hidden_costs, rental_yield, profile)

    return AuctionAnalysis(
        property_data=property_data,
        buyer_profile=profile,
        buying_power=buying_power,
        hidden_costs=hidden_costs,
        rental_yield=rental_yield,
        recommendation=recommendation,
    )
