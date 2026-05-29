# Auction Data Layer

This document describes the static JSON files in `data/` that power the auction analysis agent. Each file simulates a specific real-world data source that an auction buyer would normally check by hand before bidding.

The goal is to give the agent everything it needs to produce its four widget outputs (Buying Power, Hidden Costs, Rental Yield, Personalized Recommendation) from a single property identifier.

## Why these files exist

In production, an agent would query 10+ separate government and commercial sources to evaluate an auction property — Treasury/CWS, the Orange County Property Appraiser, Tax Collector, Comptroller, Code Enforcement, Clerk of Courts, PACER, and so on. Each source has its own access model, schema, and update cadence.

For the hackathon prototype, those sources are mocked with deterministic JSON files. The data is realistic and internally consistent across files, so the agent's reasoning behaves as it would against live data. Only one live integration exists — **RentCast** — which is called at request time for the Rental Yield widget.

## Scope

- **Geography:** Orange County, Florida (Orlando) only
- **Volume:** 20 demo auction properties
- **Scenario mix:** 6 "green" (clean), 8 "yellow" (mid-risk), 6 "red" (high-risk)
- **Cross-file consistency:** every parcel_id present in `auction_properties.json` appears in every parcel-keyed file; every address appears in `code_enforcement.json`

## File inventory

| File | Real-world equivalent | Keyed by | Records |
|---|---|---|---|
| `auction_properties.json` | Treasury/CWS auction listing | array (parcel_id) | 20 |
| `property_appraiser.json` | Orange County Property Appraiser | `parcel_id` | 20 |
| `tax_collector.json` | Orange County Tax Collector | `parcel_id` | 20 |
| `official_records.json` | Orange County Comptroller — Official Records | `parcel_id` | 20 |
| `code_enforcement.json` | City of Orlando Code Enforcement | lowercase `address` | 20 |
| `court_records.json` | Orange County Clerk of Courts | `parcel_id` | 20 |
| `auction_terms.json` | Treasury/CWS standard contract | — (single object) | 1 |
| `scenario_key.json` | **Internal testing only** | `parcel_id` | 20 |

## How files relate

```
                  auction_properties.json
                  (array of 20 properties)
                         │
                         │ parcel_id  ──────────────┐
                         │ address    ───┐          │
                         ▼               ▼          ▼
              ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
              │ property_apprai- │  │ code_enforcement │  │ tax_collector    │
              │ ser.json         │  │ .json            │  │ .json            │
              │ (by parcel_id)   │  │ (by address)     │  │ (by parcel_id)   │
              └──────────────────┘  └──────────────────┘  └──────────────────┘
                         │                                         │
                         ▼                                         ▼
              ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
              │ official_records │  │ court_records    │  │ auction_terms    │
              │ .json            │  │ .json            │  │ .json            │
              │ (by parcel_id)   │  │ (by parcel_id)   │  │ (singleton)      │
              └──────────────────┘  └──────────────────┘  └──────────────────┘
```

## File details

### 1. `auction_properties.json` — The auction listing

The "index" of all properties up for auction. This is what the agent receives an address or parcel_id against to begin analysis.

**Shape:** array of objects.

**Key fields:**
- `parcel_id` — Orange County's unique identifier, format `OC-2026-XXXX`
- `address` — full street address with ZIP
- `latitude`, `longitude` — coordinates within Orange County
- `beds`, `baths`, `sqft`, `lot_sqft`, `year_built`, `property_type`
- `auction_source` — `"Treasury/CWS"` or `"County Tax Deed"`
- `auction_date` — when bidding closes (2026-06 to 2026-08)
- `minimum_bid` — starting price
- `current_bid` — highest standing bid, or null if no bids yet
- `deposit_required` — typically 20-25% of minimum_bid
- `closing_deadline_days` — 30, 45, or 60 days after auction
- `as_is` — always true
- `financing_allowed` — usually false
- `listing_url` — link to original auction page

**Feeds:** Buying Power widget (price, deposit, deadlines), and the property identification step.

### 2. `property_appraiser.json` — Official property record

What the county officially knows about each property — owner, valuation, legal description. Mirrors what you'd find on the Orange County Property Appraiser site.

**Key fields:**
- `owner_name` — current owner of record (individuals, LLCs, or estates for distressed properties)
- `legal_description` — official lot/block/subdivision
- `assessed_value`, `land_value`, `building_value` — county tax-assessed values
- `market_estimate` — appraiser's estimated market value
- `homestead_exemption` — true if owner-occupied with homestead protection
- `last_sale_date`, `last_sale_price` — prior transfer record

**Feeds:** Buying Power widget (market value comparison), Rental Yield widget (valuation baseline).

### 3. `tax_collector.json` — Property tax status

Whether property taxes are paid, and any outstanding tax certificates. Unpaid taxes often survive the sale and become the buyer's problem.

**Key fields:**
- `annual_tax` — yearly property tax bill (~1-1.5% of assessed value)
- `unpaid_taxes` — total outstanding amount
- `delinquent` — boolean flag
- `tax_certificates` — list of tax liens sold to investors; each has year, certificate_number, amount, status
- `payment_history` — last 3 years of payment status

**Feeds:** Hidden Costs widget — unpaid taxes and certificates can survive the auction and transfer to the buyer.

### 4. `official_records.json` — Title risks

The single most important file for due diligence. Captures everything recorded against the property's title.

**Key fields:**
- `open_mortgages` — recorded mortgages; status `"Active"` or `"Released"`
- `judgments` — court judgments against the owner; can attach to property
- `municipal_liens` — city-recorded liens (code enforcement, utility, unsafe structure)
- `hoa_liens` — homeowners association assessments (Condo/Townhouse only)
- `federal_forfeiture` — federal seizure records (Treasury/CWS source only)

**Feeds:** Hidden Costs widget — the title-risk core. A red-tagged property typically has unreleased mortgages, large judgments, and municipal liens that may survive the sale.

### 5. `code_enforcement.json` — Building violations

Active code violations against the physical property. Keyed by address (not parcel_id) because code enforcement is administered at the city level by location, not by tax parcel.

**Key fields:**
- `open_violations` — list of violation records, each with case_number, opened_date, violation_type, description, fine_amount, status
- `unsafe_structure` — boolean; if true, the property may be uninhabitable or scheduled for demolition
- `open_fines_total` — sum of all open fines
- `compliance_deadline` — when violations must be remedied

**Violation types include:** overgrown lot, unsafe structure, abandoned property, expired permit, garbage accumulation, illegal addition, inoperable vehicle, pool maintenance.

**Feeds:** Hidden Costs widget — code violations and fines transfer with the property; unsafe structure rulings may require demolition or substantial repair.

### 6. `court_records.json` — Active litigation

Court cases involving the property or its owner. Mirrors the Orange County Clerk of Courts public access.

**Key fields:**
- `foreclosure_cases` — mortgage foreclosure proceedings (active or dismissed)
- `eviction_cases` — residential eviction history (signals tenant occupancy issues)
- `lawsuits` — civil cases against the owner that could affect title
- `probate` — open probate cases (when owner is deceased)

**Feeds:** Hidden Costs widget and personalized recommendation — active foreclosure, eviction, or probate cases can delay or block clean transfer.

### 7. `auction_terms.json` — Standard contract language

The same Treasury/CWS terms apply to all properties from that source, so this is a single object rather than per-property.

**Keys:**
- `deposit_rules` — how and when deposit must be paid
- `financing` — financing rules
- `as_is_clause` — disclaimer of warranties
- `title_warning` — buyer's responsibility for title
- `default_penalty` — what happens if buyer fails to close
- `closing` — closing deadlines
- `inspection` — inspection rules

**Feeds:** Personalized Recommendation widget — informs the agent about deal structure constraints.

### 8. `scenario_key.json` — Internal testing only

**Do not expose this file via the API.** It maps each `parcel_id` to a hidden scenario tag (`"green"`, `"yellow"`, `"red"`). Used only to:
- Validate the agent's recommendations during development (e.g., "the agent said green light on a red property — bug")
- Drive deterministic generation of the demo data

The agent must classify properties on its own based on the underlying data. Reading this file would defeat the purpose of having an LLM make the determination.

## Scenario mix

Properties are deliberately seeded across three risk tiers to exercise the agent's recommendation logic:

| Scenario | Count | Profile | Recommendation target |
|---|---|---|---|
| **Green** | 6 | Clean records, no unpaid taxes, no liens, no violations, fair-market priced | Green light |
| **Yellow** | 8 | One or two minor issues — small unpaid taxes, minor code violation, single judgment, possibly old dismissed foreclosure | Yellow light — needs verification |
| **Red** | 6 | Multiple serious issues — heavy unpaid taxes with certificates, active foreclosure, unsafe-structure ruling, multiple judgments, possibly federal forfeiture | Red light — avoid or bid very low |

### Example properties

A representative property from each scenario:

**GREEN — `OC-2026-1002` (2584 Mills Ave)**
- Owner: Linda Williams (individual)
- Assessed $224k, market estimate $285k
- $0 unpaid taxes, no certificates
- No active mortgages, no judgments, no liens
- No code violations, no court cases

**YELLOW — `OC-2026-1005` (6155 Rio Grande Ave)**
- Owner: Maria Jones (individual)
- Assessed $115k, market estimate $138k
- $1,392 unpaid taxes, 1 tax certificate
- 1 active mortgage, 1 small judgment
- 1 minor code violation ($789 fine)
- 1 dismissed foreclosure case (resolved)

**RED — `OC-2026-1001` (4257 Holden Ave)**
- Owner: Sunshine Holdings LLC (distressed indicator)
- Assessed $84k, market estimate $75k (below assessed — unusual)
- $18,813 unpaid taxes, 3 tax certificates
- 1 active mortgage, 3 judgments
- 1 federal forfeiture case (Treasury sale)
- 3 code violations, $4,615 in open fines
- 1 active foreclosure case, 1 active lawsuit

## Sample record

A full `auction_properties.json` entry:

```json
{
  "parcel_id": "OC-2026-1001",
  "address": "4257 Holden Ave, Orlando, FL 32839",
  "latitude": 28.591845,
  "longitude": -81.296616,
  "beds": 2,
  "baths": 1,
  "sqft": 925,
  "lot_sqft": null,
  "year_built": 1978,
  "property_type": "Condo",
  "auction_source": "Treasury/CWS",
  "auction_date": "2026-06-28",
  "minimum_bid": 61000,
  "current_bid": 66000,
  "deposit_required": 13000,
  "closing_deadline_days": 45,
  "as_is": true,
  "financing_allowed": true,
  "listing_url": "https://cwsmarketing.com/auction/oc-2026-1001"
}
```

## How the agent consumes this

The data service combines all per-property files into a single `PropertyDossier` JSON per request, served at:

```
GET /api/properties/{parcel_id}
GET /api/properties/by-address?address=...
```

The agent receives the consolidated dossier and uses it to populate the four widgets:

| Widget | Reads from |
|---|---|
| **Buying Power** | `auction_properties` + `property_appraiser` + `auction_terms` |
| **Hidden Costs** | `tax_collector` + `official_records` + `code_enforcement` + `court_records` |
| **Rental Yield** | `property_appraiser.market_estimate` + live RentCast call |
| **Personalized Recommendation** | All of the above + user financial profile |

## Live data: RentCast

Rental estimates are not in the static data — they're fetched live from [RentCast](https://www.rentcast.io) when the dossier is requested. RentCast returns rent estimate, rent range, and comparables. If `RENTCAST_API_KEY` is not configured, the rental block returns `demo_mode: true` and the rest of the dossier still works.

## Data freshness

All static files represent a snapshot as of `2026-05-28`. In production these would be refreshed on different cadences:

- Auction listings: hourly during active auctions
- Property appraiser, official records: weekly
- Tax collector: daily during tax season, weekly otherwise
- Code enforcement, court records: daily

For the prototype, the files are static.

## Maintenance

To regenerate the data with a different seed or distribution, see `scripts/build_data.py` (the generator that produced this dataset). The script uses `random.seed(42)` for reproducibility.

## Field reference quick lookup

| Need to know... | Check... |
|---|---|
| What's the minimum bid? | `auction_properties.minimum_bid` |
| Who owns the property? | `property_appraiser.owner_name` |
| What's the market estimate? | `property_appraiser.market_estimate` |
| Are taxes paid? | `tax_collector.unpaid_taxes`, `tax_collector.delinquent` |
| Are there outstanding tax certificates? | `tax_collector.tax_certificates` |
| Are there active mortgages? | `official_records.open_mortgages` (filter by `status: "Active"`) |
| Are there judgments against the owner? | `official_records.judgments` |
| Are there municipal liens? | `official_records.municipal_liens` |
| Was the property seized by the federal government? | `official_records.federal_forfeiture` |
| Are there code violations? | `code_enforcement.open_violations` |
| Is the structure unsafe? | `code_enforcement.unsafe_structure` |
| Is there active foreclosure? | `court_records.foreclosure_cases` (filter by `status: "Active"`) |
| Is the owner deceased? | `court_records.probate` (non-empty) |
| What's the rent estimate? | RentCast live call (not in static data) |
| What are the auction terms? | `auction_terms.json` |
