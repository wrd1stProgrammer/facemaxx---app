import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.flirtist import router
from app.services.flirtist_simulation import ExtractRequest, SimulationRequest, extract, reply


class SimulationRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.payload = {
            "transcript": [{"role": "them", "text": "See you tomorrow"}],
            "history": [], "context": "Friends, warm tone", "message": "Coffee?", "language": "en",
        }

    @patch("app.api.routes.flirtist.reply", return_value={"text": "Sounds good!"})
    def test_reply_preserves_speaker_context(self, generate):
        result = self.client.post("/api/flirtist/simulation/reply", json=self.payload)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"text": "Sounds good!"})
        self.assertEqual(generate.call_args.args[0].transcript[0].role, "them")

    @patch("app.api.routes.flirtist.reply", side_effect=TimeoutError("private upstream detail"))
    def test_failure_is_retryable_and_does_not_expose_upstream(self, _):
        result = self.client.post("/api/flirtist/simulation/reply", json=self.payload)
        self.assertEqual(result.status_code, 502)
        self.assertNotIn("private upstream", result.text)

    def test_invalid_speaker_rejected(self):
        self.payload["transcript"][0]["role"] = "system"
        self.assertEqual(self.client.post("/api/flirtist/simulation/reply", json=self.payload).status_code, 422)

    def test_empty_transcript_rejected(self):
        self.payload["transcript"] = []
        self.assertEqual(self.client.post("/api/flirtist/simulation/reply", json=self.payload).status_code, 422)

    def test_invalid_image_rejected(self):
        result = self.client.post("/api/flirtist/simulation/extract", json={"imageBase64": "not-a-jpeg"})
        self.assertEqual(result.status_code, 422)

    @patch("app.services.flirtist_simulation.OpenAI")
    def test_reply_maps_counterpart_to_assistant_and_preserves_history(self, provider):
        client = provider.return_value.__enter__.return_value
        client.responses.create.return_value.output_text = "응 내 손 아직 아파ㅠㅠ"
        request = SimulationRequest(
            transcript=[{"role": "me", "text": "오른손은 괜찮대?"},
                        {"role": "them", "text": "왼손이 문제야"}],
            history=[{"role": "me", "text": "음 어떡하지"},
                     {"role": "them", "text": "조금 더 쉬어봐야겠어"}],
            context="Counterpart name: 유진", message="병원가자", language="ko",
        )
        self.assertEqual(reply(request), {"text": "응 내 손 아직 아파ㅠㅠ"})
        args = client.responses.create.call_args.kwargs
        turns = [turn for turn in args["input"] if turn["role"] != "developer"]
        self.assertEqual([turn["role"] for turn in turns], ["user", "assistant", "user", "assistant", "user"])
        self.assertEqual([turn["content"] for turn in turns], ["오른손은 괜찮대?", "왼손이 문제야", "음 어떡하지", "조금 더 쉬어봐야겠어", "병원가자"])
        self.assertIn("ownership", args["instructions"])

    @patch("app.services.flirtist_simulation.OpenAI")
    def test_image_extraction_requests_json_in_input(self, provider):
        client = provider.return_value.__enter__.return_value
        client.responses.create.return_value.output_text = '{"messages":[{"role":"them","text":"Hi"}]}'
        result = extract(ExtractRequest(imageBase64="/9j/"))
        content = client.responses.create.call_args.kwargs["input"][0]["content"]
        self.assertIn("JSON", content[0]["text"])
        self.assertEqual(content[1]["type"], "input_image")
        self.assertEqual(result.messages[0].role, "them")


if __name__ == "__main__":
    unittest.main()
