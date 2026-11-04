import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

from knoa_parse.core.media import MediaProbe, MediaProbeInput, MediaStream, MediaTimeBase
from knoa_parse.processors.media.source import StagedMedia
from knoa_parse.processors.media.subtitles import FfmpegSubtitleExtractor, SubtitleExtractionError, SubtitleExtractorConfig


class SubtitleExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "source.bin"
        self.raw = b"source"
        self.path.write_bytes(self.raw)
        self.source = StagedMedia(MediaProbeInput(source_id="source", source_sha256=hashlib.sha256(self.raw).hexdigest(),
                                                  size_bytes=len(self.raw)), self.path)
        self.probe = MediaProbe(source_id="source", source_sha256=hashlib.sha256(self.raw).hexdigest(), size_bytes=len(self.raw),
                                format_name="matroska", duration_ms=1000,
                                streams=[MediaStream(index=2, kind="subtitle", time_base=MediaTimeBase(numerator=1, denominator=1000))])

    def tearDown(self):
        self.temp.cleanup()

    def test_extracts_webvtt_with_a_bounded_fake_ffmpeg(self):
        script = self.path.parent / "fake_ffmpeg.py"
        script.write_text(r"import sys; sys.stdout.buffer.write('WEBVTT\n\n00:00.000 --> 00:01.000\n字幕\n'.encode('utf-8'))", encoding="utf-8")
        track = FfmpegSubtitleExtractor(SubtitleExtractorConfig(executable=sys.executable,
                                                                executable_args=(str(script),), timeout_seconds=2)).extract(
            self.source, self.probe, 2, language="zh-CN")
        self.assertEqual(track.cues[0].text, "字幕")
        self.assertEqual(track.language, "zh-CN")

    def test_missing_subtitle_stream_is_rejected(self):
        with self.assertRaises(SubtitleExtractionError) as caught:
            FfmpegSubtitleExtractor().extract(self.source, self.probe, 1)
        self.assertEqual(caught.exception.code, "subtitle_stream_missing")


if __name__ == "__main__":
    unittest.main()
