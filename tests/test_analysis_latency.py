import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import anyio

from app.services.analysis.runner import AnalysisRunner
from app.services.ai.openai_provider import _shared_client, close_face_analysis_client, _response_text_format
from app.services.ai.payload_normalizer import FaceAnalysisPayloadNormalizer


class AnalysisLatencyTests(unittest.TestCase):
    def test_compact_wire_schema_keeps_content_and_restores_ui(self):
        schema = _response_text_format()['format']['schema']
        props = schema['$defs']['AnalysisMetric']['properties']
        self.assertIn('detail_text', props)
        self.assertIn('value_tint', props)
        self.assertNotIn('title_key', props)
        self.assertNotIn('icon_name', props)
        normalizer = FaceAnalysisPayloadNormalizer('openai', 'gpt-6-luna')
        item = normalizer._normalize_metric(dict(metric_id='canthal-tilt',
            section='proportions', value_text='5°', detail_text='Personal explanation.'),
            'proportions', 0, 'en')
        self.assertEqual(item['detail_text'], 'Personal explanation.')
        self.assertTrue(item['title_key'])
        self.assertTrue(item['icon_name'])
        self.assertEqual(item['sort_order'], 10)

    def test_original_bytes_skip_unused_signed_url(self):
        runner = AnalysisRunner.__new__(AnalysisRunner)
        runner.photo_repository = MagicMock()
        runner.photo_repository.get_photo_bytes.return_value = (b"original", "image/jpeg")
        photo_id = uuid4()
        result = runner._provider_photo_input(photo_id)
        self.assertEqual(result.photo_bytes, b"original")
        self.assertEqual(result.photo_id, photo_id)
        runner.photo_repository.get_public_photo_url.assert_not_called()

    def test_remote_only_photo_keeps_url_fallback(self):
        runner = AnalysisRunner.__new__(AnalysisRunner)
        runner.photo_repository = MagicMock()
        runner.photo_repository.get_photo_bytes.return_value = (None, "image/png")
        runner.photo_repository.get_public_photo_url.return_value = "https://example.com/photo"
        result = runner._provider_photo_input(uuid4())
        self.assertEqual(result.photo_url, "https://example.com/photo")
        runner.photo_repository.get_public_photo_url.assert_called_once()

    def test_connection_reused_and_closed_on_shutdown(self):
        async def run():
            client = SimpleNamespace(close=AsyncMock())
            _shared_client.cache_clear()
            with patch("openai.AsyncOpenAI", return_value=client) as constructor:
                with patch("app.core.config.get_settings", return_value=SimpleNamespace(openai_api_key="test")):
                    self.assertIs(_shared_client(), _shared_client())
                    constructor.assert_called_once()
                    await close_face_analysis_client()
                    client.close.assert_awaited_once()
                    self.assertEqual(_shared_client.cache_info().currsize, 0)
        anyio.run(run)
