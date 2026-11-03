import hashlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from knoa_parse.core.media import MediaProbeInput
from knoa_parse.processors.media.pyscenedetect import PySceneDetectAdapter, PySceneDetectConfig, PySceneDetectError


class _Timecode:
    def __init__(self, seconds, frames):
        self.seconds = seconds
        self.frames = frames

    def get_seconds(self):
        return self.seconds

    def get_frames(self):
        return self.frames


class PySceneDetectAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "video.mp4"
        self.data = b"synthetic video source"
        self.path.write_bytes(self.data)
        self.source = MediaProbeInput(source_id="video", source_sha256=hashlib.sha256(self.data).hexdigest(),
                                      size_bytes=len(self.data), path=self.path)

    def tearDown(self):
        self.temp.cleanup()

    def fake_module(self, scenes):
        module = types.SimpleNamespace()
        class AdaptiveDetector:
            def __init__(self, **kwargs):
                module.detector_kwargs = kwargs
        class ContentDetector:
            def __init__(self, **kwargs):
                module.detector_kwargs = kwargs
        def detect(path, detector, **kwargs):
            module.detect_args = (path, detector, kwargs)
            return scenes
        module.AdaptiveDetector = AdaptiveDetector
        module.ContentDetector = ContentDetector
        module.detect = detect
        return module

    def test_vfr_timecodes_are_mapped_to_source_milliseconds(self):
        fake = self.fake_module([
            (_Timecode(0.0, 0), _Timecode(1.333, 40)),
            (_Timecode(1.333, 40), _Timecode(3.001, 91)),
        ])
        with patch.dict(sys.modules, {"scenedetect": fake}):
            result = PySceneDetectAdapter(PySceneDetectConfig(detector="adaptive", min_scene_len_frames=12)).detect(
                self.source, duration_ms=3001)
        self.assertEqual([(scene.start_ms, scene.end_ms) for scene in result.scenes], [(0, 1333), (1333, 3001)])
        self.assertEqual(result.coverage.covered_ms, 3001)
        self.assertEqual(result.coverage.sample_count, 91)
        self.assertEqual(fake.detector_kwargs["min_scene_len"], 12)
        self.assertEqual(fake.detect_args[2]["backend"], "opencv")

    def test_content_detector_and_dependency_failure_are_explicit(self):
        fake = self.fake_module([(_Timecode(0, 0), _Timecode(1, 30))])
        with patch.dict(sys.modules, {"scenedetect": fake}):
            result = PySceneDetectAdapter(PySceneDetectConfig(detector="content", content_threshold=22)).detect(
                self.source, duration_ms=1000)
        self.assertEqual(fake.detector_kwargs["threshold"], 22)
        self.assertEqual(result.detector, "pyscenedetect-content-0.7")
        with patch("importlib.import_module", side_effect=ModuleNotFoundError("scenedetect")):
            with self.assertRaises(PySceneDetectError) as caught:
                PySceneDetectAdapter().detect(self.source, duration_ms=1000)
        self.assertEqual(caught.exception.code, "scene_dependency_missing")

    def test_invalid_result_source_change_and_config_are_rejected(self):
        fake = self.fake_module([(_Timecode(0, 0), _Timecode(2, 60))])
        with patch.dict(sys.modules, {"scenedetect": fake}):
            with self.assertRaises(PySceneDetectError) as caught:
                PySceneDetectAdapter().detect(self.source, duration_ms=1000)
        self.assertEqual(caught.exception.code, "scene_invalid_response")
        wrong = self.source.model_copy(update={"source_sha256": "0" * 64})
        with self.assertRaises(PySceneDetectError) as caught:
            PySceneDetectAdapter().detect(wrong, duration_ms=1000)
        self.assertEqual(caught.exception.code, "media_source_changed")
        with self.assertRaises(ValueError):
            PySceneDetectConfig(backend="pyav")


if __name__ == "__main__":
    unittest.main()
