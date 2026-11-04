import unittest

from knoa_parse.core.scenes import SceneEvidence, SceneSample, TimeRange
from knoa_parse.processors.media.scenes import (
    SceneDetectionError,
    SceneDetectorConfig,
    associate_scene_evidence,
    detect_scene_candidates,
)


class SceneDetectionTests(unittest.TestCase):
    def timeline(self):
        return TimeRange(start_ms=0, end_ms=4000)

    def samples(self):
        return [
            SceneSample(frame_index=0, pts_ms=0, duration_ms=500, change_score=0.0),
            SceneSample(frame_index=1, pts_ms=500, duration_ms=500, change_score=0.1),
            SceneSample(frame_index=2, pts_ms=1000, duration_ms=500, change_score=0.9),
            SceneSample(frame_index=3, pts_ms=2200, duration_ms=300, change_score=0.2),
            SceneSample(frame_index=4, pts_ms=3000, duration_ms=500, change_score=0.8),
        ]

    def test_candidates_use_actual_pts_and_make_coverage_visible(self):
        result = detect_scene_candidates("source-video", 0, self.timeline(), self.samples(),
                                         config=SceneDetectorConfig(threshold=0.5, min_scene_ms=250))
        self.assertEqual([(scene.start_ms, scene.end_ms) for scene in result.scenes],
                         [(0, 1000), (1000, 3000), (3000, 4000)])
        self.assertEqual(result.coverage.covered_ms, 2300)
        self.assertEqual(result.scenes[1].start_frame_index, 2)
        self.assertEqual(result.scenes[1].sampled_ms, 800)

    def test_short_cut_is_suppressed_and_vfr_gap_is_not_fabricated(self):
        samples = [
            SceneSample(frame_index=0, pts_ms=0, duration_ms=500, change_score=0.0),
            SceneSample(frame_index=1, pts_ms=500, duration_ms=100, change_score=0.9),
            SceneSample(frame_index=2, pts_ms=700, duration_ms=500, change_score=0.9),
        ]
        result = detect_scene_candidates("source-video", 0, TimeRange(start_ms=0, end_ms=2000), samples,
                                         config=SceneDetectorConfig(threshold=0.5, min_scene_ms=500))
        self.assertEqual(len(result.scenes), 2)
        self.assertEqual(result.scenes[0].end_ms, 500)
        self.assertEqual(result.coverage.covered_ms, 1100)
        self.assertEqual(result.scenes[1].sampled_ms, 600)

    def test_empty_samples_are_explicitly_uncovered(self):
        result = detect_scene_candidates("source-video", 1, self.timeline(), [])
        self.assertEqual(result.coverage.sample_count, 0)
        self.assertEqual(result.coverage.covered_ms, 0)
        self.assertEqual(len(result.scenes), 1)
        self.assertEqual(result.scenes[0].sampled_ms, 0)

    def test_invalid_order_range_and_duplicate_samples_are_rejected(self):
        samples = self.samples()
        for candidate in (list(reversed(samples)), samples[:2] + [samples[1]]):
            with self.assertRaises(SceneDetectionError) as caught:
                detect_scene_candidates("source-video", 0, self.timeline(), candidate)
            self.assertEqual(caught.exception.code, "scene_invalid_timeline")
        out = [SceneSample(frame_index=0, pts_ms=3900, duration_ms=200, change_score=0.0)]
        with self.assertRaises(SceneDetectionError) as caught:
            detect_scene_candidates("source-video", 0, self.timeline(), out)
        self.assertEqual(caught.exception.code, "scene_invalid_timeline")

    def test_evidence_links_only_when_intervals_overlap(self):
        result = detect_scene_candidates("source-video", 0, self.timeline(), self.samples(),
                                         config=SceneDetectorConfig(threshold=0.5, min_scene_ms=250))
        evidence = [
            SceneEvidence(id="t1", source_id="source-video", kind="transcript", start_ms=1100, end_ms=1200),
            SceneEvidence(id="s1", source_id="source-video", kind="subtitle", start_ms=3500, end_ms=3600),
            SceneEvidence(id="gap", source_id="source-video", kind="audio", start_ms=1200, end_ms=1500),
        ]
        links = associate_scene_evidence(result.scenes, evidence)
        self.assertEqual(links[0].evidence_ids, [])
        self.assertEqual(links[1].evidence_ids, ["t1", "gap"])
        self.assertEqual(links[2].evidence_ids, ["s1"])

    def test_duplicate_scene_or_evidence_ids_are_rejected(self):
        result = detect_scene_candidates("source-video", 0, self.timeline(), self.samples())
        duplicate = [SceneEvidence(id="same", source_id="source-video", kind="audio", start_ms=0, end_ms=1)] * 2
        with self.assertRaises(SceneDetectionError) as caught:
            associate_scene_evidence(result.scenes, duplicate)
        self.assertEqual(caught.exception.code, "scene_duplicate_id")


if __name__ == "__main__":
    unittest.main()
