import unittest

from auction_agent.data import PROPERTIES
from auction_agent.official_data import apply_official_overrides


class OfficialDataTest(unittest.TestCase):
    def test_official_override_keeps_required_fields_with_fallback_or_live_data(self):
        data = dict(PROPERTIES["6013-fender-court"])
        updated = apply_official_overrides(data)

        self.assertIn("official_data_status", updated)
        self.assertGreater(updated["current_bid"], 0)
        self.assertGreater(updated["required_deposit"], 0)


if __name__ == "__main__":
    unittest.main()
