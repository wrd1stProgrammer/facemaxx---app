import unittest

from app.services.ai.payload_normalizer import FaceAnalysisPayloadNormalizer


class RingDisplayValueTests(unittest.TestCase):
    def test_ring_display_is_always_derived_from_progress(self):
        normalizer = FaceAnalysisPayloadNormalizer('openai', 'gpt-6-luna')
        for raw in ('8.2 · Balanced', 'Balanced', '9.9', '0.99', '', None):
            with self.subTest(raw=raw):
                ring = normalizer._normalize_ring(
                    dict(metric_id='symmetry', score=0.82, display_value=raw),
                    'aesthetics', 0)
                self.assertEqual(ring['display_value'], '8.2')
                self.assertEqual(ring['score'], 0.82)

    def test_endpoints_remain_numeric(self):
        normalizer = FaceAnalysisPayloadNormalizer('openai', 'gpt-6-luna')
        for score, expected in ((0, '0.0'), (1, '10.0')):
            self.assertEqual(normalizer._score_display_value('Description', score), expected)
