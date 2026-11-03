import hashlib
import importlib.util
import os
import shutil
import subprocess
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
from knoa_parse.processors.media.ffmpeg import FfmpegAudioExtractor, FfmpegConfig
from knoa_parse.processors.media.pyscenedetect import PySceneDetectAdapter, PySceneDetectConfig
from knoa_parse.processors.media.timeline import plan_audio_chunks


def _ffprobe_path():
    return os.environ.get("KNOA_FFPROBE") or shutil.which("ffprobe")


def _ffmpeg_path():
    return os.environ.get("KNOA_FFMPEG") or shutil.which("ffmpeg")


@unittest.skipUnless(cv2 is not None and numpy is not None and importlib.util.find_spec("scenedetect")
                     and _ffprobe_path() and _ffmpeg_path(),
                     "Install the video extra and set KNOA_FFPROBE/KNOA_FFMPEG for real toolchain checks")
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

    def test_real_ffmpeg_extracts_a_bounded_audio_chunk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-av.mp4"
            command = [_ffmpeg_path(), "-y", "-v", "error", "-f", "lavfi", "-i",
                       "color=c=black:s=64x64:r=10:d=2", "-f", "lavfi", "-i",
                       "sine=frequency=440:duration=2", "-shortest", "-c:v", "mpeg4", "-c:a", "aac",
                       "-pix_fmt", "yuv420p", str(path)]
            created = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                     timeout=30, check=False)
            self.assertEqual(created.returncode, 0, created.stderr.decode(errors="replace"))
            data = path.read_bytes()
            source = MediaProbeInput(source_id="synthetic-av", source_sha256=hashlib.sha256(data).hexdigest(),
                                     size_bytes=len(data), path=path)
            probe = FfprobeMediaProber(FfprobeConfig(executable=_ffprobe_path())).probe(source)
            audio_stream = next(stream for stream in probe.streams if stream.kind == "audio")
            chunk = plan_audio_chunks(source.source_id, probe, audio_stream.index,
                                      max_segment_ms=1000, overlap_ms=100)[0]
            segment = FfmpegAudioExtractor(FfmpegConfig(executable=_ffmpeg_path())).extract(source, chunk)
            self.assertEqual(segment.artifact.media_type, "audio/wav")
            self.assertTrue(segment.content.startswith(b"RIFF"))
            self.assertGreater(segment.artifact.size_bytes, 1000)


if __name__ == "__main__":
    unittest.main()
