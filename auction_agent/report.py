"""Text report rendering for voice and CLI output."""

from __future__ import annotations

from auction_agent.engine import AuctionAnalysis


def render_report(analysis: AuctionAnalysis) -> str:
    prop = analysis.property_data
    buying = analysis.buying_power
    hidden = analysis.hidden_costs
    rental = analysis.rental_yield
    rec = analysis.recommendation

    hidden_lines = [
        f"- {item['source']}: {item['status'].replace('_', ' ')} "
        f"({item['risk_level']} risk). {item['finding']}"
        for item in hidden.checklist
        if item["status"] in {"risk_found", "needs_review", "not_checked"}
    ]
    next_steps = [f"{index}. {step}" for index, step in enumerate(rec.next_steps, start=1)]

    return "\n".join(
        [
            f"Property: {prop['address']}, {prop['city']}, {prop['state']}",
            "",
            "Auction Status:",
            f"{prop['auction_type']}. Current bid is ${prop['current_bid']:,.0f}; "
            f"required deposit is ${prop['required_deposit']:,.0f}; closing deadline is "
            f"{prop['closing_deadline_days']} days. Sale is as-is and should be treated "
            "as no-financing-contingency until verified.",
            _official_status_line(prop),
            "",
            "Buying Power:",
            buying.summary,
            f"Financing feasible within timeline: {'yes' if buying.financing_feasible else 'no'}",
            "",
            "Hidden Costs:",
            hidden.summary,
            *hidden_lines,
            "",
            "Rental Yield:",
            rental.summary,
            f"Monthly rent estimate: ${rental.monthly_rent:,.0f}",
            f"Monthly expenses estimate: ${rental.monthly_expenses:,.0f}",
            f"Break-even rent: ${rental.break_even_rent:,.0f}",
            f"Cash-on-cash return estimate: {rental.cash_on_cash_return:.1%}",
            "",
            "Legal / Title Risk:",
            "High until official records, court records, forfeiture documents, taxes, and code "
            "violations are reviewed. This is the main reason the recommendation is cautious.",
            "",
            f"Recommendation: {rec.category}",
            rec.summary,
            "",
            f"Maximum Safe Bid: ${rec.max_safe_bid:,.0f}",
            f"Do Not Bid Above: ${rec.do_not_bid_above:,.0f}",
            f"Biggest Risk: {rec.biggest_risk}",
            "",
            "Next Steps:",
            *next_steps,
        ]
)


def _official_status_line(prop: dict) -> str:
    status = prop.get("official_data_status")
    if not status:
        return "Official data: seeded fallback."
    if status.get("status") == "verified":
        return f"Official data: verified from Treasury page ({status.get('url')})."
    return f"Official data: unavailable live; using fallback. Reason: {status.get('error', 'unknown')}"
