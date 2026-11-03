import hashlib
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

try:
    import cv2
    import numpy
except ImportError:  # The video extra is intentionally optional in the base environment.
    cv2 = None
    numpy = None

from knoa_parse.core.media import MediaProbeInput
from knoa_parse.processors.media.ffprobe import FfprobeConfig, FfprobeMediaProber
from knoa_parse.processors.media.pyscenedetect import PySceneDetectAdapter, PySceneDetectConfig


def _ffprobe_path():
    return os.environ.get("KNOA_FFPROBE") or shutil.which("ffprobe")


@unittest.skipUnless(cv2 is not None and numpy is not None and importlib.util.find_spec("scenedetect")
                     and _ffprobe_path(), "Install the video extra and set KNOA_FFPROBE for real toolchain checks")
class OptionalVideoToolchainTests(unittest.TestCase):
    def test_real_ffprobe_and_pyscenedetect_preserve_synthetic_vfr_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 64))
            self.assertTrue(writer.isOpened())
            for _ in range(10):
                writer.write(255 * numpy.ones((64, 64, 3), dtype="uint8"))
            for _ in range(10):
                writer.write(numpy.zeros((64, 64, 3), dtype="uint8"))
            writer.release()
            data = path.read_bytes()
            source = MediaProbeInput(source_id="synthetic-video", source_sha256=hashlib.sha256(data).hexdigest(),
                                     size_bytes=len(data), path=path)
            probe = FfprobeMediaProber(FfprobeConfig(executable=_ffprobe_path())).probe(
                source, include_frames=True, stream_index=0)
            self.assertEqual(probe.duration_ms, 2000)
            self.assertEqual(len(probe.frames), 20)
            self.assertEqual([frame.pts_ms for frame in probe.frames[:3]], [0, 100, 200])
            scenes = PySceneDetectAdapter(PySceneDetectConfig(detector="content", content_threshold=1,
                                                              min_scene_len_frames=1)).detect(
                source, duration_ms=probe.duration_ms, stream_index=0)
            self.assertEqual([(scene.start_ms, scene.end_ms) for scene in scenes.scenes], [(0, 1000), (1000, 2000)])
            self.assertEqual(scenes.coverage.covered_ms, probe.duration_ms)


if __name__ == "__main__":
    unittest.main()
