import unittest

from actions.actions import ActionAnalyzeAuctionProperty


class FakeTracker:
    def __init__(self, slots):
        self.slots = slots

    def get_slot(self, key):
        return self.slots.get(key)


class FakeDispatcher:
    def __init__(self):
        self.messages = []

    def utter_message(self, text):
        self.messages.append(text)



class RasaActionTest(unittest.TestCase):
    def test_rasa_action_returns_auction_report(self):
        action = ActionAnalyzeAuctionProperty()
        dispatcher = FakeDispatcher()
        tracker = FakeTracker(
            {
                "property_address": "6013 Fender Court",
                "city": "Orlando",
            "current_bid": "170000",
                "available_cash": "40000",
                "investment_goal": "long-term rental",
                "financing_type": "hard money or DSCR loan",
                "estimated_repairs": "5000",
                "market_rent": "2200",
            }
        )

        events = action.run(dispatcher, tracker, {})

        self.assertEqual(events, [])
        self.assertTrue(dispatcher.messages)
        self.assertIn("Maximum Safe Bid", dispatcher.messages[0])
        self.assertIn("Recommendation:", dispatcher.messages[0])


if __name__ == "__main__":
    unittest.main()
