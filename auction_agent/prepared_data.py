"""Adapter for the prepared multi-source auction data under data/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_prepared_property(identifier: str | None) -> dict[str, Any] | None:
    """Load a property from the prepared data files and normalize it for widgets."""
    if not identifier:
        return None

    properties = _load_json("auction_properties.json")
    listing = _find_listing(properties, identifier)
    if not listing:
        return None

    parcel_id = listing["parcel_id"]
    appraiser = _load_json("property_appraiser.json").get(parcel_id, {})
    taxes = _load_json("tax_collector.json").get(parcel_id, {})
    records = _load_json("official_records.json").get(parcel_id, {})
    courts = _load_json("court_records.json").get(parcel_id, {})
    code = _load_json("code_enforcement.json").get(listing["address"].lower(), {})
    terms = _load_json("auction_terms.json")

    current_bid = listing["current_bid"] or listing["minimum_bid"]
    rent = _estimate_rent(listing, appraiser)
    return {
        "property_id": parcel_id,
        "parcel_number": parcel_id,
        "address": _street_only(listing["address"]),
        "full_address": listing["address"],
        "city": "Orlando",
        "county": "Orange County",
        "state": "FL",
        "auction_type": listing["auction_source"],
        "auction_url": listing["listing_url"],
        "current_bid": current_bid,
        "estimated_after_repair_value": appraiser.get("market_estimate") or current_bid,
        "estimated_market_rent": rent,
        "airbnb_monthly_revenue": round(rent * 1.35),
        "estimated_repairs": _estimate_repairs(code, records, courts),
        "repair_condition": _repair_condition(code),
        "required_deposit": listing["deposit_required"],
        "closing_deadline_days": listing["closing_deadline_days"],
        "minimum_bid": listing["minimum_bid"],
        "auction_date": listing["auction_date"],
        "inspection_dates": terms.get("inspection", "Inspection terms require auction-package review."),
        "living_area_sqft": listing["sqft"],
        "site_area_sqft": listing["lot_sqft"] or 0,
        "year_built": listing["year_built"],
        "bedrooms": listing["beds"],
        "bathrooms": listing["baths"],
        "zoning": listing["property_type"],
        "auction_terms": {
            "as_is": listing["as_is"],
            "financing_contingency": listing["financing_allowed"],
            "default_penalty": terms.get("default_penalty", "Deposit may be forfeited."),
            "buyer_responsibilities": [
                terms.get("title_warning", "Buyer must verify title and liens."),
                terms.get("as_is_clause", "Property is sold as-is."),
            ],
        },
        "annual_property_taxes": taxes.get("annual_tax") or 0,
        "annual_insurance_estimate": _estimate_insurance(listing),
        "monthly_hoa": _estimate_hoa(listing, records),
        "hoa_notes": _hoa_notes(records),
        "property_management_rate": 0.08,
        "vacancy_rate": 0.07,
        "closing_cost_rate": 0.035,
        "down_payment_rate": 0.25,
        "hard_money_interest_rate": 0.12,
        "loan_term_years": 30,
        "official_research": _build_checklist(listing, appraiser, taxes, records, code, courts, terms),
        "prepared_sources": {
            "auction_listing": listing,
            "property_appraiser": appraiser,
            "tax_collector": taxes,
            "official_records": records,
            "code_enforcement": code,
            "court_records": courts,
        },
        "official_data_status": {
            "status": "prepared_dataset",
            "url": listing["listing_url"],
            "summary": "Loaded from prepared multi-source auction dataset.",
        },
    }


def list_prepared_properties() -> list[dict[str, Any]]:
    return _load_json("auction_properties.json")


def _load_json(filename: str) -> Any:
    return json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))


def _find_listing(properties: list[dict[str, Any]], identifier: str) -> dict[str, Any] | None:
    needle = identifier.strip().lower()
    for item in properties:
        if item["parcel_id"].lower() == needle:
            return item
        if needle in item["address"].lower():
            return item
    return None


def _street_only(address: str) -> str:
    return address.split(",")[0]


def _estimate_rent(listing: dict[str, Any], appraiser: dict[str, Any]) -> int:
    market = appraiser.get("market_estimate") or listing["minimum_bid"]
    bedroom_floor = max(1, int(listing["beds"])) * 525
    value_based = round((market * 0.009) / 12)
    sqft_based = round(listing["sqft"] * 1.45)
    return max(1_200, bedroom_floor, value_based, sqft_based)


def _estimate_repairs(code: dict[str, Any], records: dict[str, Any], courts: dict[str, Any]) -> int:
    base = 8_000
    if code.get("unsafe_structure"):
        base += 45_000
    base += len(code.get("open_violations", [])) * 4_000
    base += min(code.get("open_fines_total", 0), 20_000)
    if records.get("federal_forfeiture"):
        base += 5_000
    if courts.get("eviction_cases"):
        base += 3_500
    return base


def _repair_condition(code: dict[str, Any]) -> str:
    if code.get("unsafe_structure"):
        return "high repair risk; unsafe structure flag present"
    if code.get("open_violations"):
        return "moderate repair risk; open code violations present"
    return "low visible repair risk in prepared records"


def _estimate_insurance(listing: dict[str, Any]) -> int:
    base = 2_400 if listing["property_type"] != "Condo" else 1_600
    age_penalty = max(0, 2026 - int(listing["year_built"]) - 25) * 45
    return round(base + age_penalty)


def _estimate_hoa(listing: dict[str, Any], records: dict[str, Any]) -> int:
    if listing["property_type"] in {"Condo", "Townhouse"}:
        return 325
    if records.get("hoa_liens"):
        return 175
    return 0


def _hoa_notes(records: dict[str, Any]) -> str:
    hoa_liens = records.get("hoa_liens", [])
    if not hoa_liens:
        return "No HOA lien in prepared official-record data."
    total = sum(item.get("amount", 0) for item in hoa_liens)
    return f"{len(hoa_liens)} HOA lien(s) totaling about ${total:,.0f} in prepared records."


def _build_checklist(
    listing: dict[str, Any],
    appraiser: dict[str, Any],
    taxes: dict[str, Any],
    records: dict[str, Any],
    code: dict[str, Any],
    courts: dict[str, Any],
    terms: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        _item("Auction Listing", "verified", "medium", f"{listing['auction_source']} listing found for {listing['parcel_id']} with current bid ${listing['current_bid'] or listing['minimum_bid']:,.0f}, deposit ${listing['deposit_required']:,.0f}, and {listing['closing_deadline_days']}-day close.", "Confirms auction facts, timing, deposit, and payment pressure.", listing["listing_url"]),
        _item("Auction Terms", "risk_found" if not listing["financing_allowed"] else "verified", "high" if not listing["financing_allowed"] else "medium", terms.get("financing", "Financing terms require review."), "Auction terms determine whether the buyer can safely close.", listing["listing_url"]),
        _item("Property Appraiser", "verified", "low", f"Owner {appraiser.get('owner_name', 'unknown')}; assessed value ${appraiser.get('assessed_value', 0):,.0f}; market estimate ${appraiser.get('market_estimate', 0):,.0f}.", "Confirms public property characteristics and valuation baseline.", "https://ocpaweb.ocpafl.org/"),
        _item("Tax Collector", "risk_found" if taxes.get("delinquent") else "verified", "high" if taxes.get("unpaid_taxes", 0) > 5_000 else "medium" if taxes.get("delinquent") else "low", f"Unpaid taxes ${taxes.get('unpaid_taxes', 0):,.0f}; {len(taxes.get('tax_certificates', []))} tax certificate(s).", "Unpaid taxes and certificates can change real acquisition cost.", "https://www.octaxcol.com/taxes/"),
        _item("Official Records", _status_for_records(records), _risk_for_records(records), _records_summary(records), "Recorded liens, judgments, mortgages, and forfeiture are core title risk.", "https://or.occompt.com/recorder/eagleweb/docSearch.jsp"),
        _item("Code Enforcement", "risk_found" if code.get("open_violations") else "verified", "high" if code.get("unsafe_structure") else "medium" if code.get("open_violations") else "low", f"{len(code.get('open_violations', []))} open violation(s); open fines ${code.get('open_fines_total', 0):,.0f}; unsafe structure: {'yes' if code.get('unsafe_structure') else 'no'}.", "Code issues can create fines, repairs, or occupancy blockers.", "https://www.orlando.gov/Building-Development/Code-Enforcement"),
        _item("Court Records", _status_for_courts(courts), _risk_for_courts(courts), _court_summary(courts), "Foreclosure, eviction, lawsuits, and probate affect transfer risk.", "https://myeclerk.myorangeclerk.com/"),
    ]


def _item(source: str, status: str, risk: str, finding: str, why: str, url: str) -> dict[str, str]:
    return {"source": source, "status": status, "risk_level": risk, "finding": finding, "why_it_matters": why, "url": url}


def _status_for_records(records: dict[str, Any]) -> str:
    active_mortgages = any(item.get("status") == "Active" for item in records.get("open_mortgages", []))
    if active_mortgages or records.get("judgments") or records.get("municipal_liens") or records.get("hoa_liens") or records.get("federal_forfeiture"):
        return "risk_found"
    return "verified"


def _risk_for_records(records: dict[str, Any]) -> str:
    severe = len(records.get("judgments", [])) + len(records.get("municipal_liens", [])) + len(records.get("federal_forfeiture", []))
    active_mortgages = sum(1 for item in records.get("open_mortgages", []) if item.get("status") == "Active")
    if severe >= 2 or active_mortgages >= 2:
        return "high"
    if severe or active_mortgages:
        return "medium"
    return "low"


def _records_summary(records: dict[str, Any]) -> str:
    active_mortgages = sum(1 for item in records.get("open_mortgages", []) if item.get("status") == "Active")
    return f"{active_mortgages} active mortgage(s), {len(records.get('judgments', []))} judgment(s), {len(records.get('municipal_liens', []))} municipal lien(s), {len(records.get('hoa_liens', []))} HOA lien(s), {len(records.get('federal_forfeiture', []))} forfeiture record(s)."


def _status_for_courts(courts: dict[str, Any]) -> str:
    if courts.get("foreclosure_cases") or courts.get("eviction_cases") or courts.get("lawsuits") or courts.get("probate"):
        return "risk_found"
    return "verified"


def _risk_for_courts(courts: dict[str, Any]) -> str:
    active_cases = [*courts.get("foreclosure_cases", []), *courts.get("eviction_cases", []), *courts.get("lawsuits", []), *courts.get("probate", [])]
    active_count = sum(1 for item in active_cases if item.get("status") in {"Active", "Writ issued", "Open"})
    if active_count >= 2:
        return "high"
    if active_count == 1:
        return "medium"
    return "low"


def _court_summary(courts: dict[str, Any]) -> str:
    return f"{len(courts.get('foreclosure_cases', []))} foreclosure case(s), {len(courts.get('eviction_cases', []))} eviction case(s), {len(courts.get('lawsuits', []))} lawsuit(s), {len(courts.get('probate', []))} probate case(s)."
