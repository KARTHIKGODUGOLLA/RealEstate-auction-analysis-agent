import unittest

from auction_agent.web import _is_collection_prompt, _is_unhelpful_rasa_answer, _local_advisor_reply


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
        self.assertIn("maximum safe bid", reply["text"])
        self.assertIn("not bid above", reply["text"])

    def test_local_chat_fallback_answers_risk_questions(self):
        reply = _local_advisor_reply(
            "What could go wrong with this property?",
            {"parcelId": "6013-fender-court", "availableCash": "40000"},
        )

        self.assertIn("main issue", reply["text"])
        self.assertIn("Highest-priority checks", reply["text"])

    def test_collection_prompt_detection_catches_rasa_slot_questions(self):
        self.assertTrue(_is_collection_prompt(["What repair budget should I assume?"]))
        self.assertFalse(_is_collection_prompt(["Your maximum safe bid is $114,035."]))

    def test_unhelpful_rasa_answer_detection_catches_context_failures(self):
        self.assertTrue(_is_unhelpful_rasa_answer(["I can't calculate your maximum safe bid."]))
        self.assertFalse(_is_unhelpful_rasa_answer(["Your maximum safe bid is $114,035."]))


if __name__ == "__main__":
    unittest.main()
