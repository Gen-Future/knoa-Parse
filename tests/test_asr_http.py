import base64
import hashlib
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from knoa_parse.core.asr import AsrRequest, PreparedAudioSegment
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Artifact
from knoa_parse.providers.asr.http import AsrProviderError, HttpAsrConfig, HttpAsrProvider


class _AsrServer(BaseHTTPRequestHandler):
    status = 200
    response = {"provider": "remote-asr", "model": "remote-v1", "language": "zh", "segments": [{
        "start_ms": 100, "end_ms": 800, "text": "你好世界", "words": [
            {"start_ms": 100, "end_ms": 300, "text": "你好"},
            {"start_ms": 320, "end_ms": 800, "text": "世界", "speaker": "spk-1"},
        ],
    }], "usage": {"input_ms": 1200, "cost_micros": 5}}
    calls = []
    redirect = None

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.calls.append((self.path, dict(self.headers), body))
        if self.redirect:
            self.send_response(307)
            self.send_header("Location", self.redirect)
            self.end_headers()
            return
        raw = self.response if isinstance(self.response, bytes) else json.dumps(self.response).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        pass


class AsrHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _AsrServer)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def setUp(self):
        _AsrServer.calls.clear()
        _AsrServer.status = 200
        _AsrServer.response = {"provider": "remote-asr", "model": "remote-v1", "language": "zh", "segments": [{
            "start_ms": 100, "end_ms": 800, "text": "你好世界", "words": [
                {"start_ms": 100, "end_ms": 300, "text": "你好"},
                {"start_ms": 320, "end_ms": 800, "text": "世界", "speaker": "spk-1"},
            ],
        }], "usage": {"input_ms": 1200, "cost_micros": 5}}
        _AsrServer.redirect = None
        self.audio = b"synthetic audio bytes"
        artifact = Artifact(id="audio-segment", role="derived", media_type="audio/wav",
                            sha256=hashlib.sha256(self.audio).hexdigest(), size_bytes=len(self.audio))
        segment = PreparedAudioSegment(source_id="source-audio", source_sha256="a" * 64,
                                       source_artifact_id="source-audio", stream_index=2, start_ms=1000,
                                       end_ms=3000, artifact=artifact, content=self.audio)
        self.request = AsrRequest(segment=segment, language="zh", word_timestamps=True, diarization=True,
                                  timeout_seconds=2, trace_id="trace-asr", idempotency_key="idem-1")
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.provider = HttpAsrProvider(HttpAsrConfig(provider="test-asr", base_url=self.base,
                                                       api_key="synthetic-secret", allow_local_http=True,
                                                       max_response_bytes=4096))

    def test_request_and_segment_offsets_are_mapped_to_source_timeline(self):
        result = self.provider.transcribe(self.request)
        self.assertEqual(result.source_id, "source-audio")
        self.assertEqual(result.stream_index, 2)
        self.assertEqual(result.segments[0].start_ms, 1100)
        self.assertEqual(result.segments[0].end_ms, 1800)
        self.assertEqual(result.segments[0].words[0].start_ms, 1100)
        self.assertEqual(result.segments[0].words[1].speaker, "spk-1")
        path, headers, body = _AsrServer.calls[0]
        self.assertEqual(path, "/transcribe")
        self.assertEqual(headers["Authorization"], "Bearer synthetic-secret")
        self.assertEqual(headers["Idempotency-Key"], "idem-1")
        payload = json.loads(body)
        self.assertEqual(base64.b64decode(payload["audio_base64"]), self.audio)
        self.assertEqual(payload["start_ms"], 1000)
        self.assertNotIn("source-audio", body.decode())

    def test_capability_is_external_and_does_not_expose_key(self):
        capability = self.provider.describe()
        self.assertEqual(capability.execution, "external_service")
        self.assertTrue(capability.word_timestamps)
        self.assertNotIn("synthetic-secret", capability.model_dump_json())

    def test_https_is_default_and_local_http_is_explicit(self):
        with self.assertRaises(ValueError):
            HttpAsrConfig(provider="x", base_url="http://example.com", api_key="x")
        with self.assertRaises(ValueError):
            HttpAsrConfig(provider="x", base_url="https://example.com?key=x", api_key="x")

    def test_invalid_request_and_limits_fail_before_network(self):
        bad = self.request.model_copy(deep=True)
        bad.segment.artifact = bad.segment.artifact.model_copy(update={"sha256": "b" * 64})
        with self.assertRaises(AsrProviderError) as caught:
            self.provider.transcribe(bad)
        self.assertEqual(caught.exception.code, "provider_invalid_request")
        limited = HttpAsrProvider(HttpAsrConfig(provider="test-asr", base_url=self.base, api_key="x",
                                                  allow_local_http=True, max_segment_bytes=1))
        with self.assertRaises(AsrProviderError) as caught:
            limited.transcribe(self.request)
        self.assertEqual(caught.exception.code, "provider_request_limit")
        self.assertEqual(_AsrServer.calls, [])

    def test_invalid_segments_words_usage_and_offsets_are_rejected(self):
        cases = [
            {"segments": [{"start_ms": 0, "end_ms": 1, "text": " "}], "usage": {}},
            {"segments": [{"start_ms": 0, "end_ms": 1, "text": "x", "words": [{"start_ms": 0, "end_ms": 2, "text": "x"}]}], "usage": {}},
            {"segments": [{"start_ms": 3000, "end_ms": 3001, "text": "x"}], "usage": {}},
            {"segments": [], "usage": {"cost_micros": -1}},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                _AsrServer.response = {"provider": "x", "model": "m", **extra}
                with self.assertRaises(AsrProviderError) as caught:
                    self.provider.transcribe(self.request)
                self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_status_errors_redirect_and_invalid_json_are_sanitized(self):
        for status, code, retryable in ((401, "provider_auth_failed", False), (408, "provider_timeout", True),
                                        (429, "provider_rate_limited", True), (500, "provider_unavailable", True),
                                        (400, "provider_invalid_request", False)):
            with self.subTest(status=status):
                _AsrServer.status = status
                _AsrServer.response = b"secret-provider-error"
                with self.assertRaises(AsrProviderError) as caught:
                    self.provider.transcribe(self.request)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn("secret-provider", str(caught.exception))
        _AsrServer.status = 200
        _AsrServer.response = b"not-json"
        with self.assertRaises(AsrProviderError) as caught:
            self.provider.transcribe(self.request)
        self.assertEqual(caught.exception.code, "provider_invalid_response")
        _AsrServer.response = {"provider": "x", "model": "m", "segments": [], "usage": {}}
        _AsrServer.calls.clear()
        _AsrServer.redirect = "/other"
        with self.assertRaises(AsrProviderError) as caught:
            self.provider.transcribe(self.request)
        self.assertEqual(caught.exception.code, "provider_redirect")
        self.assertEqual(len(_AsrServer.calls), 1)

    def test_adapter_stays_out_of_parse_result_contract(self):
        self.assertNotIsInstance(self.provider.transcribe(self.request), ParseError)


if __name__ == "__main__":
    unittest.main()
