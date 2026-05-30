import unittest

from auction_agent.web import (
    _is_collection_prompt,
    _is_too_long_for_voice,
    _is_unhelpful_rasa_answer,
    _local_advisor_reply,
    _spotlight_card,
    _should_use_demo_answer,
)
from auction_agent.engine import analyze_auction


class WebChatFallbackTest(unittest.TestCase):
    def test_local_chat_fallback_answers_max_bid_questions(self):
        reply = _local_advisor_reply(
            "Explain my maximum safe bid.",
            {
                "parcelId": "6013-fender-court",
                "currentBid": "170000",
                "availableCash": "40000",
                "investmentGoal": "long-term rental",
                "financingType": "hard money or DSCR loan",
            },
        )

        self.assertEqual(reply["source"], "local-demo-fallback")
        self.assertIn("Max safe bid", reply["text"])
        self.assertIn("not bid above", reply["text"])

    def test_local_chat_fallback_answers_risk_questions(self):
        reply = _local_advisor_reply(
            "What could go wrong with this property?",
            {"parcelId": "6013-fender-court", "availableCash": "40000"},
        )

        self.assertIn("Main risk", reply["text"])
        self.assertIn("Check", reply["text"])

    def test_collection_prompt_detection_catches_rasa_slot_questions(self):
        self.assertTrue(_is_collection_prompt(["What repair budget should I assume?"]))
        self.assertFalse(_is_collection_prompt(["Your maximum safe bid is $114,035."]))

    def test_unhelpful_rasa_answer_detection_catches_context_failures(self):
        self.assertTrue(_is_unhelpful_rasa_answer(["I can't calculate your maximum safe bid."]))
        self.assertFalse(_is_unhelpful_rasa_answer(["Your maximum safe bid is $114,035."]))

    def test_voice_demo_prefers_concise_answers(self):
        self.assertTrue(_should_use_demo_answer("Explain my maximum safe bid for this selected property."))
        self.assertTrue(_is_too_long_for_voice(["x" * 901]))
        self.assertFalse(_is_too_long_for_voice(["short answer"]))

    def test_spotlight_card_has_demo_metrics(self):
        card = _spotlight_card(analyze_auction(use_official_data=False))

        self.assertIn("address", card)
        self.assertIn("score", card)
        self.assertIn("cash_gap", card)
        self.assertIn("monthly_cash_flow", card)


if __name__ == "__main__":
    unittest.main()
