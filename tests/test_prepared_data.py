import unittest

from auction_agent.engine import analyze_auction
from auction_agent.prepared_data import list_prepared_properties, load_prepared_property


class PreparedDataTest(unittest.TestCase):
    def test_can_load_prepared_property_by_parcel_id(self):
        data = load_prepared_property("OC-2026-1001")

        self.assertIsNotNone(data)
        self.assertEqual(data["property_id"], "OC-2026-1001")
        self.assertGreater(data["current_bid"], 0)
        self.assertTrue(data["official_research"])

    def test_engine_can_analyze_prepared_property(self):
        analysis = analyze_auction("OC-2026-1002", use_official_data=False)

        self.assertEqual(analysis.property_data["property_id"], "OC-2026-1002")
        self.assertIn(analysis.recommendation.category, {"Green light", "Yellow light", "Red light"})

    def test_properties_endpoint_source_has_twenty_records(self):
        self.assertEqual(len(list_prepared_properties()), 20)


if __name__ == "__main__":
    unittest.main()
