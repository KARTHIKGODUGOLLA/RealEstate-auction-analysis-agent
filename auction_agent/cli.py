"""Command-line entry point for the auction analysis demo."""

from __future__ import annotations

import argparse

from auction_agent.engine import analyze_auction
from auction_agent.report import render_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a seeded auction property.")
    parser.add_argument(
        "command",
        choices=["analyze"],
        help="Run the auction due diligence analysis.",
    )
    parser.add_argument(
        "--property-id",
        default="6013-fender-court",
        help="Seeded property id to analyze.",
    )
    args = parser.parse_args()

    result = analyze_auction(args.property_id)
    print(render_report(result))


if __name__ == "__main__":
    main()
