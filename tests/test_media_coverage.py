import unittest

from knoa_parse.core.asr import AsrUsage
from knoa_parse.core.media_results import MediaChunkOutcome
from knoa_parse.processors.media.coverage import MediaCoverageError, require_audio_stream, summarize_execution
from tests.test_media_timeline import _probe


class MediaCoverageTests(unittest.TestCase):
    def test_audio_preflight_rejects_no_audio_and_returns_stream(self):
        self.assertEqual(require_audio_stream(_probe()), 1)
        with self.assertRaises(MediaCoverageError) as caught:
            require_audio_stream(_probe(audio=False))
        self.assertEqual(caught.exception.code, "media_audio_required")

    def test_full_coverage_is_completed_and_known_cost_is_summed(self):
        outcomes = [
            MediaChunkOutcome(chunk_id="a", core_start_ms=0, core_end_ms=500, status="completed"),
            MediaChunkOutcome(chunk_id="b", core_start_ms=500, core_end_ms=1000, status="completed"),
        ]
        summary = summarize_execution("transcribe", 0, 1000, outcomes,
                                     [AsrUsage(input_ms=500, cost_micros=2), AsrUsage(input_ms=500, cost_micros=3)])
        self.assertEqual(summary.coverage.status, "completed")
        self.assertEqual(summary.coverage.missing_ranges, [])
        self.assertEqual(summary.cost.cost_micros, 5)
        self.assertEqual(summary.cost.billing_state, "known")

    def test_failed_chunk_exposes_missing_range_and_partial_status(self):
        outcomes = [
            MediaChunkOutcome(chunk_id="a", core_start_ms=0, core_end_ms=500, status="completed"),
            MediaChunkOutcome(chunk_id="b", core_start_ms=500, core_end_ms=1000, status="failed", issue_code="provider_timeout"),
        ]
        summary = summarize_execution("transcribe", 0, 1000, outcomes, [AsrUsage(input_ms=500, cost_micros=None)])
        self.assertEqual(summary.coverage.status, "partial")
        self.assertEqual(summary.coverage.missing_ranges, [[500, 1000]])
        self.assertIsNone(summary.cost.cost_micros)
        self.assertEqual(summary.cost.billing_state, "unknown")

    def test_no_sent_work_is_failed_and_not_sent_cost(self):
        summary = summarize_execution("transcribe", 0, 1000, [], [])
        self.assertEqual(summary.coverage.status, "failed")
        self.assertEqual(summary.cost.billing_state, "not_sent")
        self.assertIsNone(summary.cost.cost_micros)

    def test_overlap_duplicate_and_invalid_target_are_rejected(self):
        outcomes = [
            MediaChunkOutcome(chunk_id="a", core_start_ms=0, core_end_ms=600, status="completed"),
            MediaChunkOutcome(chunk_id="b", core_start_ms=500, core_end_ms=1000, status="completed"),
        ]
        with self.assertRaises(MediaCoverageError) as caught:
            summarize_execution("transcribe", 0, 1000, outcomes, [])
        self.assertEqual(caught.exception.code, "media_overlap")
        with self.assertRaises(MediaCoverageError) as caught:
            summarize_execution("other", 0, 1000, [], [])
        self.assertEqual(caught.exception.code, "media_invalid_target")


if __name__ == "__main__":
    unittest.main()
