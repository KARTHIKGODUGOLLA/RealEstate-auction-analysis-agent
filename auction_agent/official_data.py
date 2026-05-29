"""Official-source fetchers for auction due diligence.

The goal is pragmatic: use official government pages when reachable, and keep a
seeded fallback so the hackathon demo never dies because a county portal blocks
automation or requires a captcha.
"""

from __future__ import annotations

import re
import ssl
from html import unescape
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen


OFFICIAL_SOURCE_DIRECTORY = [
    {
        "name": "Treasury Auction Page",
        "url": "https://www.treasury.gov/auctions/treasury/rp/6013fender.shtml",
        "mode": "live_fetch",
        "checks": ["auction date", "deposit", "starting bid", "parcel number", "taxes", "as-is terms"],
    },
    {
        "name": "Orange County Property Appraiser",
        "url": "https://ocpaweb.ocpafl.org/",
        "mode": "guided_official_search",
        "checks": ["parcel id", "owner", "legal description", "assessed value", "property characteristics"],
    },
    {
        "name": "Orange County Tax Collector",
        "url": "https://www.octaxcol.com/taxes/",
        "mode": "guided_official_search",
        "checks": ["tax balance", "tax certificates", "delinquent bills", "annual taxes"],
    },
    {
        "name": "Orange County Comptroller Official Records",
        "url": "https://or.occompt.com/recorder/eagleweb/docSearch.jsp",
        "mode": "guided_official_search",
        "checks": ["deeds", "mortgages", "releases", "liens", "judgments", "lis pendens"],
    },
    {
        "name": "Orange County Clerk of Courts",
        "url": "https://myeclerk.myorangeclerk.com/",
        "mode": "guided_official_search",
        "checks": ["foreclosure", "civil lawsuits", "judgments", "evictions", "probate"],
    },
    {
        "name": "City of Orlando Code Enforcement",
        "url": "https://www.orlando.gov/Building-Development/Code-Enforcement",
        "mode": "guided_official_search",
        "checks": ["open violations", "fines", "unsafe structure", "compliance deadlines"],
    },
    {
        "name": "PACER",
        "url": "https://pacer.uscourts.gov/",
        "mode": "guided_official_search",
        "checks": ["federal forfeiture case", "sale order", "claims by other parties"],
    },
]


def fetch_treasury_auction(url: str) -> dict[str, Any]:
    """Fetch and parse the official Treasury auction page."""
    try:
        request = Request(url, headers={"User-Agent": "AuctionAdvisorHackathon/0.1"})
        try:
            with urlopen(request, timeout=8) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except URLError as exc:
            if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
                raise
            context = ssl._create_unverified_context()
            with urlopen(request, timeout=8, context=context) as response:
                html = response.read().decode("utf-8", errors="ignore")
    except (OSError, URLError) as exc:
        return {
            "status": "unavailable",
            "url": url,
            "error": str(exc),
            "fields": {},
            "summary": "Official Treasury page could not be fetched; using seeded fallback.",
        }

    text = _clean_html(html)
    fields = {
        "address": _match(text, r"(6013 Fender Court,\s*Orlando,\s*Florida\s*32837)"),
        "auction_date": _match(text, r"Auction Date and Time:\s*([^\\n]+?ET)"),
        "deposit": _money(_match(text, r"Deposit:\s*\$([0-9,]+)")),
        "starting_bid": _money(_match(text, r"Starting Bid:\s*\$([0-9,]+)")),
        "living_area_sqft": _number(_match(text, r"Living Area:\s*([0-9,]+)")),
        "site_area_sqft": _number(_match(text, r"Site Area:\s*([0-9,]+)")),
        "year_built": _number(_match(text, r"Year Built:\s*([0-9]{4})")),
        "county": _match(text, r"County:\s*([A-Za-z ]+)"),
        "annual_property_taxes": _money(_match(text, r"2024 County Taxes:\s*\$([0-9,]+)")),
        "parcel_number": _match(text, r"Parcel No:\s*([0-9\\-]+)"),
        "zoning": _match(text, r"Zoning:\s*([^\\n]+)"),
        "hoa_quarterly": _money(_match(text, r"HOA Dues:\s*\$([0-9,.]+)")),
        "sale_number": _match(text, r"Sale Number:\s*([0-9\\-]+)"),
    }
    fields = {key: value for key, value in fields.items() if value not in {None, ""}}
    return {
        "status": "verified",
        "url": url,
        "fields": fields,
        "summary": "Fetched live official Treasury auction page.",
    }


def apply_official_overrides(property_data: dict[str, Any]) -> dict[str, Any]:
    """Return property data updated from official sources when available."""
    official = fetch_treasury_auction(property_data["auction_url"])
    if official["status"] != "verified":
        property_data["official_data_status"] = official
        return property_data

    fields = official["fields"]
    if fields.get("starting_bid"):
        property_data["current_bid"] = fields["starting_bid"]
        property_data["minimum_bid"] = fields["starting_bid"]
    if fields.get("deposit"):
        property_data["required_deposit"] = fields["deposit"]
    if fields.get("annual_property_taxes"):
        property_data["annual_property_taxes"] = fields["annual_property_taxes"]
    if fields.get("parcel_number"):
        property_data["parcel_number"] = fields["parcel_number"]
    if fields.get("living_area_sqft"):
        property_data["living_area_sqft"] = fields["living_area_sqft"]
    if fields.get("site_area_sqft"):
        property_data["site_area_sqft"] = fields["site_area_sqft"]
    if fields.get("year_built"):
        property_data["year_built"] = fields["year_built"]
    if fields.get("zoning"):
        property_data["zoning"] = fields["zoning"]
    if fields.get("auction_date"):
        property_data["auction_date"] = fields["auction_date"]
    if fields.get("hoa_quarterly"):
        property_data["monthly_hoa"] = round(fields["hoa_quarterly"] / 3)
    property_data["official_data_status"] = official
    return property_data


def _clean_html(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "\n", text)
    text = unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n+", "\n", text)
    return text


def _match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _money(value: str | None) -> int | None:
    if value is None:
        return None
    return round(float(value.replace(",", "")))


def _number(value: str | None) -> int | None:
    if value is None:
        return None
    return int(value.replace(",", ""))
