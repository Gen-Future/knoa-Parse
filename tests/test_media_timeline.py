import hashlib
import unittest

from knoa_parse.core.media import MediaProbe, MediaStream, MediaTimeBase
from knoa_parse.processors.media.timeline import MediaTimelineError, parse_subtitle_track, plan_audio_chunks


def _probe(duration=10000, audio=True):
    streams = []
    if audio:
        streams.append(MediaStream(index=1, kind="audio", time_base=MediaTimeBase(numerator=1, denominator=48000),
                                   sample_rate=48000, channels=2, duration_ms=duration))
    streams.append(MediaStream(index=0, kind="video", time_base=MediaTimeBase(numerator=1, denominator=90000),
                               width=1280, height=720, duration_ms=duration))
    return MediaProbe(source_id="source", source_sha256=hashlib.sha256(b"x").hexdigest(), size_bytes=1,
                      format_name="mp4", duration_ms=duration, streams=streams)


class MediaTimelineTests(unittest.TestCase):
    def test_audio_chunks_tile_core_ranges_and_bound_request_size(self):
        chunks = plan_audio_chunks("source", _probe(), 1, max_segment_ms=4000, overlap_ms=500)
        self.assertEqual([(item.request_start_ms, item.request_end_ms) for item in chunks],
                         [(0, 3500), (2500, 6500), (5500, 9500), (8500, 10000)])
        self.assertEqual([(item.core_start_ms, item.core_end_ms) for item in chunks],
                         [(0, 3000), (3000, 6000), (6000, 9000), (9000, 10000)])
        self.assertTrue(all(item.request_end_ms - item.request_start_ms <= 4000 for item in chunks))

    def test_no_audio_stream_and_missing_duration_are_explicit_failures(self):
        with self.assertRaises(MediaTimelineError) as caught:
            plan_audio_chunks("source", _probe(audio=False), 1, max_segment_ms=1000)
        self.assertEqual(caught.exception.code, "media_audio_stream_missing")
        with self.assertRaises(MediaTimelineError) as caught:
            plan_audio_chunks("source", _probe(duration=None), 1, max_segment_ms=1000)
        self.assertEqual(caught.exception.code, "media_duration_missing")

    def test_overlap_and_segment_limits_are_bounded(self):
        for kwargs in ({"max_segment_ms": 0}, {"max_segment_ms": 1000, "overlap_ms": 500}):
            with self.assertRaises(MediaTimelineError) as caught:
                plan_audio_chunks("source", _probe(), 1, **kwargs)
            self.assertEqual(caught.exception.code, "media_invalid_request")

    def test_srt_and_vtt_timestamps_and_multiline_text_are_preserved(self):
        srt = "1\n00:00:01,000 --> 00:00:02,250\n第一行\n第二行\n\n"
        result = parse_subtitle_track("source", srt, format="srt", language="zh")
        self.assertEqual(result.cues[0].start_ms, 1000)
        self.assertEqual(result.cues[0].end_ms, 2250)
        self.assertEqual(result.cues[0].text, "第一行\n第二行")
        vtt = "WEBVTT\n\n00:01.000 --> 00:02.000 align:start\nHello\n"
        vtt_result = parse_subtitle_track("source", vtt, format="vtt")
        self.assertEqual(vtt_result.cues[0].start_ms, 1000)

    def test_subtitle_invalid_header_timestamp_and_range_are_rejected(self):
        cases = [("bad", "vtt", "subtitle_invalid_header"),
                 ("WEBVTT\n\n00:60.000 --> 00:61.000\nx", "vtt", "subtitle_invalid_timestamp"),
                 ("1\n00:00:02,000 --> 00:00:01,000\nx", "srt", "subtitle_invalid_cue")]
        for text, format, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(MediaTimelineError) as caught:
                    parse_subtitle_track("source", text, format=format)
                self.assertEqual(caught.exception.code, code)

    def test_subtitle_cues_are_not_silently_reordered(self):
        text = "1\n00:00:02,000 --> 00:00:03,000\nlate\n\n2\n00:00:01,000 --> 00:00:01,500\nearly\n"
        with self.assertRaises(MediaTimelineError) as caught:
            parse_subtitle_track("source", text, format="srt")
        self.assertEqual(caught.exception.code, "subtitle_invalid_cue")


if __name__ == "__main__":
    unittest.main()
