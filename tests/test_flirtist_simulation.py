import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.flirtist import router
from app.services.flirtist_simulation import ExtractRequest, extract


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
