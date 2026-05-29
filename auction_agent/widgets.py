"""The four auction due diligence widgets."""

from __future__ import annotations

from dataclasses import dataclass
from math import pow
from typing import Any


@dataclass(frozen=True)
class BuyingPowerResult:
    available_cash: int
    required_deposit: int
    estimated_closing_costs: int
    estimated_repairs: int
    emergency_reserve: int
    cash_needed_at_current_bid: int
    remaining_cash_at_current_bid: int
    max_safe_bid: int
    do_not_bid_above: int
    financing_feasible: bool
    risk_level: str
    summary: str


@dataclass(frozen=True)
class HiddenCostsResult:
    risk_level: str
    high_risk_count: int
    medium_risk_count: int
    risk_found_count: int
    needs_review_count: int
    summary: str
    checklist: list[dict[str, Any]]


@dataclass(frozen=True)
class RentalYieldResult:
    purchase_price: int
    total_project_cost: int
    monthly_rent: int
    monthly_expenses: int
    monthly_cash_flow: int
    annual_noi: int
    cap_rate: float
    cash_on_cash_return: float
    break_even_rent: int
    max_bid_for_target_return: int
    summary: str


@dataclass(frozen=True)
class RecommendationResult:
    category: str
    score: int
    max_safe_bid: int
    do_not_bid_above: int
    biggest_risk: str
    summary: str
    next_steps: list[str]


def analyze_buying_power(property_data: dict[str, Any], profile: dict[str, Any]) -> BuyingPowerResult:
    current_bid = property_data["current_bid"]
    available_cash = profile["available_cash"]
    emergency_reserve = profile["minimum_emergency_reserve"]
    required_deposit = property_data["required_deposit"]
    estimated_repairs = property_data["estimated_repairs"]
    closing_cost_rate = property_data["closing_cost_rate"]
    down_payment_rate = property_data["down_payment_rate"]
    estimated_closing_costs = round(current_bid * closing_cost_rate)

    required_equity = max(required_deposit, round(current_bid * down_payment_rate))
    financed_cash_needed = required_equity + estimated_closing_costs + estimated_repairs + emergency_reserve
    remaining_cash = available_cash - financed_cash_needed

    deposit_threshold_bid = required_deposit / down_payment_rate
    cash_after_repairs_and_reserve = available_cash - estimated_repairs - emergency_reserve
    max_bid_if_deposit_controls = (cash_after_repairs_and_reserve - required_deposit) / closing_cost_rate
    if max_bid_if_deposit_controls <= deposit_threshold_bid:
        max_safe_bid = max(0, round(max_bid_if_deposit_controls))
    else:
        max_safe_bid = max(0, round(cash_after_repairs_and_reserve / (down_payment_rate + closing_cost_rate)))
    do_not_bid_above = round(max_safe_bid * 1.08)

    financing_feasible = property_data["closing_deadline_days"] >= 30 and remaining_cash >= 0
    if remaining_cash < 0:
        risk_level = "high"
    elif remaining_cash < 5_000:
        risk_level = "medium"
    else:
        risk_level = "low"

    summary = (
        f"At the current bid, estimated cash needed is ${financed_cash_needed:,.0f}, "
        f"leaving ${remaining_cash:,.0f}. The safe max bid is about ${max_safe_bid:,.0f} "
        "because the deposit, repairs, closing costs, and reserve consume most of the "
        "$40,000 cash position."
    )

    return BuyingPowerResult(
        available_cash=available_cash,
        required_deposit=required_deposit,
        estimated_closing_costs=estimated_closing_costs,
        estimated_repairs=estimated_repairs,
        emergency_reserve=emergency_reserve,
        cash_needed_at_current_bid=financed_cash_needed,
        remaining_cash_at_current_bid=remaining_cash,
        max_safe_bid=max_safe_bid,
        do_not_bid_above=do_not_bid_above,
        financing_feasible=financing_feasible,
        risk_level=risk_level,
        summary=summary,
    )


def analyze_hidden_costs(property_data: dict[str, Any]) -> HiddenCostsResult:
    checklist = property_data["official_research"]
    high_risk_count = sum(1 for item in checklist if item["risk_level"] == "high")
    medium_risk_count = sum(1 for item in checklist if item["risk_level"] == "medium")
    risk_found_count = sum(1 for item in checklist if item["status"] == "risk_found")
    needs_review_count = sum(1 for item in checklist if item["status"] in {"needs_review", "not_checked"})

    if risk_found_count >= 2 or high_risk_count >= 3:
        risk_level = "high"
    elif needs_review_count >= 4:
        risk_level = "medium-high"
    else:
        risk_level = "medium"

    summary = (
        f"Hidden-cost risk is {risk_level}. {risk_found_count} source(s) already show risk "
        f"and {needs_review_count} source(s) still need review before bidding."
    )

    return HiddenCostsResult(
        risk_level=risk_level,
        high_risk_count=high_risk_count,
        medium_risk_count=medium_risk_count,
        risk_found_count=risk_found_count,
        needs_review_count=needs_review_count,
        summary=summary,
        checklist=checklist,
    )


def analyze_rental_yield(property_data: dict[str, Any], purchase_price: int) -> RentalYieldResult:
    repairs = property_data["estimated_repairs"]
    closing_costs = round(purchase_price * property_data["closing_cost_rate"])
    total_project_cost = purchase_price + repairs + closing_costs
    monthly_rent = property_data["estimated_market_rent"]
    monthly_taxes = round(property_data["annual_property_taxes"] / 12)
    monthly_insurance = round(property_data["annual_insurance_estimate"] / 12)
    monthly_hoa = property_data["monthly_hoa"]
    management = round(monthly_rent * property_data["property_management_rate"])
    vacancy = round(monthly_rent * property_data["vacancy_rate"])
    debt_service = _monthly_payment(
        principal=round(purchase_price * (1 - property_data["down_payment_rate"])),
        annual_rate=property_data["hard_money_interest_rate"],
        years=property_data["loan_term_years"],
    )

    monthly_expenses = monthly_taxes + monthly_insurance + monthly_hoa + management + vacancy + debt_service
    monthly_cash_flow = monthly_rent - monthly_expenses
    annual_operating_expenses = (monthly_taxes + monthly_insurance + monthly_hoa + management + vacancy) * 12
    annual_noi = (monthly_rent * 12) - annual_operating_expenses
    cap_rate = annual_noi / total_project_cost
    cash_invested = round(purchase_price * property_data["down_payment_rate"]) + closing_costs + repairs
    cash_on_cash_return = (monthly_cash_flow * 12) / cash_invested
    break_even_rent = monthly_expenses
    max_bid_for_target_return = _max_bid_for_target_cap_rate(
        annual_noi=annual_noi,
        repairs=repairs,
        closing_cost_rate=property_data["closing_cost_rate"],
        target_cap_rate=0.08,
    )

    summary = (
        f"At a ${purchase_price:,.0f} bid, estimated cash flow is ${monthly_cash_flow:,.0f}/month "
        f"with a {cap_rate:.1%} cap rate. The rental only works if repairs stay near "
        f"${repairs:,.0f} and rent reaches about ${monthly_rent:,.0f}/month."
    )

    return RentalYieldResult(
        purchase_price=purchase_price,
        total_project_cost=total_project_cost,
        monthly_rent=monthly_rent,
        monthly_expenses=monthly_expenses,
        monthly_cash_flow=monthly_cash_flow,
        annual_noi=annual_noi,
        cap_rate=cap_rate,
        cash_on_cash_return=cash_on_cash_return,
        break_even_rent=break_even_rent,
        max_bid_for_target_return=max_bid_for_target_return,
        summary=summary,
    )


def make_recommendation(
    buying_power: BuyingPowerResult,
    hidden_costs: HiddenCostsResult,
    rental_yield: RentalYieldResult,
    profile: dict[str, Any],
) -> RecommendationResult:
    buying_score = 30
    if buying_power.risk_level == "high":
        buying_score = 8
    elif buying_power.risk_level == "medium":
        buying_score = 18

    hidden_score = 30
    if hidden_costs.risk_level == "high":
        hidden_score = 6
    elif hidden_costs.risk_level == "medium-high":
        hidden_score = 12

    yield_score = 25
    if rental_yield.monthly_cash_flow < 0:
        yield_score = 8
    elif rental_yield.cap_rate < 0.07:
        yield_score = 15

    profile_score = 15
    if "first-time" in profile["experience"] and hidden_costs.high_risk_count >= 3:
        profile_score = 6

    score = buying_score + hidden_score + yield_score + profile_score
    if score >= 80:
        category = "Green light"
    elif score >= 50:
        category = "Yellow light"
    else:
        category = "Red light"

    biggest_risk = (
        "unresolved legal/title and auction-term risk"
        if hidden_costs.high_risk_count >= 3
        else "cash reserve pressure after closing"
    )
    summary = (
        f"{category}. This may be worth pursuing only with verification. "
        f"Your safe max bid is ${buying_power.max_safe_bid:,.0f}; do not bid above "
        f"${buying_power.do_not_bid_above:,.0f} without clean title, confirmed taxes, "
        "and financing locked before the auction deadline."
    )
    next_steps = [
        "Verify property taxes and tax certificates.",
        "Search official records for liens, unreleased mortgages, judgments, and HOA claims.",
        "Check city and county code violations.",
        "Confirm whether any liens or taxes survive the auction sale.",
        "Confirm financing and cash-to-close before placing a bid.",
    ]

    return RecommendationResult(
        category=category,
        score=score,
        max_safe_bid=buying_power.max_safe_bid,
        do_not_bid_above=buying_power.do_not_bid_above,
        biggest_risk=biggest_risk,
        summary=summary,
        next_steps=next_steps,
    )


def _monthly_payment(principal: int, annual_rate: float, years: int) -> int:
    monthly_rate = annual_rate / 12
    number_of_payments = years * 12
    payment = principal * (monthly_rate * pow(1 + monthly_rate, number_of_payments)) / (
        pow(1 + monthly_rate, number_of_payments) - 1
    )
    return round(payment)


def _max_bid_for_target_cap_rate(
    annual_noi: int,
    repairs: int,
    closing_cost_rate: float,
    target_cap_rate: float,
) -> int:
    max_project_cost = annual_noi / target_cap_rate
    return round((max_project_cost - repairs) / (1 + closing_cost_rate))
