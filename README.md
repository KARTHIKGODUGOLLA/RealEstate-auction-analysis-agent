# Auction Analysis Agent

Voice-first auction due diligence assistant for deciding whether to bid, how much
to bid, and what could go wrong.

This repo starts with the analysis engine. It is intentionally small: one seeded
property, one buyer profile, and four deterministic widgets that produce a clear
recommendation.

## Quickstart: Web Demo

The web UI is the best hackathon demo surface.

```bash
python3 -m auction_agent.web
```

Then open http://127.0.0.1:8787

The dashboard has two paths:
- `Analyze auction` calls the local deterministic engine directly.
- `Rasa conversation` sends the selected property and form assumptions to Rasa at
  `localhost:5005`, so run `make run-actions` and `make rasa` first.

## CLI

```bash
python3 -m auction_agent.cli analyze
```

## Rasa Layer

This repo now includes a Rasa CALM flow and custom action wrapper around the
analysis engine:

```bash
cp .env.example .env
# Fill NEBIUS_API_KEY from Token Factory.
# Recommended command-generator model:
# NEBIUS_MODEL_ID=Qwen/Qwen3-235B-A22B-Instruct-2507

# Rasa requires Python >=3.10,<3.12. Use Python 3.11.
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[rasa]"

set -a
source .env
set +a

make list-nebius-models
make check-nebius
make train
make run-actions
make rasa
```

The flow collects auction details, calls `action_analyze_auction_property`, saves
the buyer profile, stores the completed analysis in `.data/`, and returns the
same four-widget recommendation used by the UI.

## Current Slice

- Buying Power: safe max bid, cash needed, reserve pressure.
- Hidden Costs: official-source checklist and risk summary.
- Rental Yield: cash flow, cap rate, cash-on-cash, break-even rent.
- Personalized Recommendation: Green / Yellow / Red with max bid guidance.
- Web UI: editable deal assumptions, browser voice input, four-widget cockpit.
- Rasa flow/action: structured intake, deterministic analysis, persistent memory.
- Prepared data adapter: supports the merged 20-property multi-source dataset by
  `parcel_id` without exposing `scenario_key.json`.

## Demo Prompt

```text
Analyze this auction property in Orlando: 6013 Fender Court. I have around
$40,000 cash and want to know if I should bid and my maximum bid.
```

## Next Integrations

- Wrap `auction_agent.engine.analyze_auction()` in a Rasa custom action.
- Add an MCP server for official checklist and hidden-cost research tools.
- Connect the existing starter voice loop to the Rasa flow.
