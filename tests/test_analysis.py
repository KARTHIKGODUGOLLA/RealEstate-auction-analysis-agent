import unittest

from auction_agent.engine import analyze_auction


class AuctionAnalysisTest(unittest.TestCase):
    def test_analysis_returns_yellow_or_red_for_first_time_buyer_with_unresolved_risk(self):
        analysis = analyze_auction(use_official_data=False)

        self.assertIn(analysis.recommendation.category, {"Yellow light", "Red light"})
        self.assertGreater(analysis.recommendation.max_safe_bid, 0)
        self.assertGreaterEqual(analysis.hidden_costs.high_risk_count, 3)

    def test_buying_power_respects_cash_constraint(self):
        analysis = analyze_auction(use_official_data=False)

        self.assertEqual(analysis.buying_power.available_cash, 40_000)
        self.assertLess(analysis.buying_power.max_safe_bid, analysis.property_data["current_bid"])
        self.assertGreater(analysis.buying_power.do_not_bid_above, analysis.buying_power.max_safe_bid)

    def test_rental_yield_has_core_metrics(self):
        analysis = analyze_auction(use_official_data=False)

        self.assertGreater(analysis.rental_yield.monthly_rent, 0)
        self.assertEqual(analysis.rental_yield.break_even_rent, analysis.rental_yield.monthly_expenses)
        self.assertGreater(analysis.rental_yield.total_project_cost, analysis.rental_yield.purchase_price)


if __name__ == "__main__":
    unittest.main()
