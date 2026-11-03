import hashlib
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from knoa_parse.core.media import MediaProbeInput
from knoa_parse.processors.media.ffprobe import FfprobeConfig, FfprobeMediaProber, MediaProbeError


def _valid_payload():
    return {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "start_time": "-0.25", "duration": "12.345"},
        "streams": [
            {"index": 0, "codec_type": "video", "codec_name": "h264", "time_base": "1/90000",
             "start_pts": "0", "duration_ts": "1080000", "duration": "12.000", "width": "1920",
             "height": "1080", "r_frame_rate": "30000/1001", "avg_frame_rate": "2997/100", "nb_frames": "360"},
            {"index": 1, "codec_type": "audio", "codec_name": "aac", "time_base": "1/48000",
             "start_pts": "0", "duration_ts": "576000", "duration": "12.000", "sample_rate": "48000",
             "channels": "2"},
        ],
    }


class FfprobeMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_path = self.root / "sample.bin"
        self.source = b"synthetic media bytes; ffprobe output is authored for the adapter test"
        self.source_path.write_bytes(self.source)
        self.identity = MediaProbeInput(source_id="source-media", source_sha256=hashlib.sha256(self.source).hexdigest(),
                                        size_bytes=len(self.source), path=self.source_path)

    def tearDown(self):
        self.temp.cleanup()

    def prober(self, payload, *, code=0, sleep=0, raw=False, max_output_bytes=16 * 1024 * 1024, timeout=2,
               max_frames=200_000):
        script = self.root / "fake_ffprobe.py"
        if raw:
            output = payload
        else:
            output = json.dumps(payload, separators=(",", ":"))
        script.write_text(textwrap.dedent(f"""
            import sys, time
            time.sleep({sleep!r})
            sys.stdout.write({output!r})
            sys.exit({code})
        """), encoding="utf-8")
        return FfprobeMediaProber(FfprobeConfig(
            executable=sys.executable, executable_args=(str(script),), timeout_seconds=timeout,
            max_output_bytes=max_output_bytes, max_frames=max_frames,
        ))

    def test_probe_preserves_stream_shape_time_base_and_serializable_identity(self):
        probe = self.prober(_valid_payload()).probe(self.identity)
        self.assertEqual(probe.format_name, "mov,mp4,m4a,3gp,3g2,mj2")
        self.assertEqual(probe.start_ms, -250)
        self.assertEqual(probe.duration_ms, 12345)
        self.assertEqual(probe.streams[0].time_base.denominator, 90000)
        self.assertEqual(probe.streams[0].average_frame_rate.numerator, 2997)
        self.assertEqual(probe.streams[1].sample_rate, 48000)
        self.assertNotIn("sample.bin", self.identity.model_dump_json())

    def test_frames_preserve_pts_instead_of_inventing_fixed_fps(self):
        payload = _valid_payload()
        payload["frames"] = [
            {"stream_index": 0, "best_effort_timestamp": "0", "pkt_duration": "3003", "key_frame": 1},
            {"stream_index": 0, "best_effort_timestamp": "4504", "pkt_duration": "3003", "key_frame": 0},
        ]
        result = self.prober(payload).probe(self.identity, include_frames=True, stream_index=0)
        self.assertEqual([frame.pts for frame in result.frames], [0, 4504])
        self.assertEqual([frame.pts_ms for frame in result.frames], [0, 50])
        self.assertEqual(result.frames[0].key_frame, True)

    def test_invalid_identity_is_rejected_before_tool_execution(self):
        wrong = self.identity.model_copy(update={"source_sha256": "0" * 64})
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(_valid_payload()).probe(wrong)
        self.assertEqual(caught.exception.code, "media_source_changed")

    def test_missing_tool_timeout_and_nonzero_exit_are_stable(self):
        with self.assertRaises(MediaProbeError) as caught:
            FfprobeMediaProber(FfprobeConfig(executable=str(self.root / "missing-ffprobe"))).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_tool_missing")
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(_valid_payload(), sleep=0.5, timeout=0.1).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_tool_timeout")
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(_valid_payload(), code=7).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_probe_failed")

    def test_output_and_frame_limits_fail_before_unbounded_result(self):
        with self.assertRaises(MediaProbeError) as caught:
            self.prober("x" * 4097, raw=True, max_output_bytes=4096).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_probe_limit")
        payload = _valid_payload()
        payload["frames"] = [{"stream_index": 0, "best_effort_timestamp": "0"}] * 3
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(payload, max_frames=2).probe(self.identity, include_frames=True)
        self.assertEqual(caught.exception.code, "media_probe_invalid_response")

    def test_malformed_stream_geometry_or_frames_are_rejected(self):
        payload = _valid_payload()
        del payload["streams"][0]["width"]
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(payload).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_probe_invalid_response")
        payload = _valid_payload()
        payload["frames"] = [{"stream_index": 9, "best_effort_timestamp": "0"}]
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(payload).probe(self.identity, include_frames=True)
        self.assertEqual(caught.exception.code, "media_probe_invalid_response")

    def test_duplicate_json_and_unknown_frame_pts_do_not_pass(self):
        raw = '{"format":{"format_name":"x"},"format":{"format_name":"y"},"streams":[]}'
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(raw, raw=True).probe(self.identity)
        self.assertEqual(caught.exception.code, "media_probe_invalid_response")
        payload = _valid_payload()
        payload["frames"] = [{"stream_index": 0, "best_effort_timestamp": "not-a-number"}]
        with self.assertRaises(MediaProbeError) as caught:
            self.prober(payload).probe(self.identity, include_frames=True)
        self.assertEqual(caught.exception.code, "media_probe_invalid_response")


if __name__ == "__main__":
    unittest.main()
