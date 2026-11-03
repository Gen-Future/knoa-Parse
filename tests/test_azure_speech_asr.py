import hashlib
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from knoa_parse.core.asr import AsrRequest, PreparedAudioSegment
from knoa_parse.core.models import Artifact
from knoa_parse.providers.asr.azure_speech import AzureSpeechConfig, AzureSpeechError, AzureSpeechFastTranscriptionProvider


class _SpeechServer(BaseHTTPRequestHandler):
    status = 200
    response = {"durationMilliseconds": 2000, "phrases": [{
        "offsetMilliseconds": 40, "durationMilliseconds": 320, "text": "你好",
        "speaker": 1, "words": [{"offsetMilliseconds": 40, "durationMilliseconds": 160, "text": "你"},
                                  {"offsetMilliseconds": 220, "durationMilliseconds": 140, "text": "好"}],
    }]}
    calls = []

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.calls.append((self.path, dict(self.headers), body))
        raw = self.response if isinstance(self.response, bytes) else json.dumps(self.response).encode()
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        pass


class AzureSpeechTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _SpeechServer)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def setUp(self):
        _SpeechServer.calls.clear()
        _SpeechServer.status = 200
        _SpeechServer.response = {"durationMilliseconds": 2000, "phrases": [{
            "offsetMilliseconds": 40, "durationMilliseconds": 320, "text": "你好", "speaker": 1,
            "words": [{"offsetMilliseconds": 40, "durationMilliseconds": 160, "text": "你"},
                      {"offsetMilliseconds": 220, "durationMilliseconds": 140, "text": "好"}],
        }]}
        audio = b"synthetic wav bytes"
        artifact = Artifact(id="segment", role="derived", media_type="audio/wav",
                            sha256=hashlib.sha256(audio).hexdigest(), size_bytes=len(audio))
        segment = PreparedAudioSegment(source_id="source", source_sha256="a" * 64, source_artifact_id="source",
                                       stream_index=1, start_ms=1000, end_ms=3000, artifact=artifact, content=audio)
        self.request = AsrRequest(segment=segment, language="zh-CN", word_timestamps=True, diarization=True,
                                  timeout_seconds=2, trace_id="trace", idempotency_key="id")
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.provider = AzureSpeechFastTranscriptionProvider(AzureSpeechConfig(
            endpoint=self.base, api_key="synthetic-secret", allow_local_http=True, max_response_bytes=4096))

    def test_multipart_request_and_absolute_offsets(self):
        response = self.provider.transcribe(self.request)
        self.assertEqual(response.provider, "azure-speech")
        self.assertEqual(response.segments[0].start_ms, 1040)
        self.assertEqual(response.segments[0].words[1].end_ms, 1360)
        path, headers, body = _SpeechServer.calls[0]
        self.assertIn("/speechtotext/transcriptions:transcribe", path)
        self.assertIn("api-version=2025-10-15", path)
        self.assertEqual(headers["Ocp-Apim-Subscription-Key"], "synthetic-secret")
        self.assertIn(b'name="definition"', body)
        self.assertIn(b'"locales":["zh-CN"]', body)
        self.assertIn(b'"wordLevelTimestampsEnabled":true', body)
        self.assertNotIn(b"source", body)

    def test_capability_config_and_request_limits(self):
        self.assertEqual(self.provider.describe().version, "2025-10-15")
        with self.assertRaises(ValueError):
            AzureSpeechConfig(endpoint="http://example.com", api_key="x")
        with self.assertRaises(ValueError):
            AzureSpeechConfig(endpoint=self.base, api_key="x", allow_local_http=True, api_version="v3.2")
        limited = AzureSpeechFastTranscriptionProvider(AzureSpeechConfig(endpoint=self.base, api_key="x",
                                                                          allow_local_http=True, max_segment_bytes=1))
        with self.assertRaises(AzureSpeechError) as caught:
            limited.transcribe(self.request)
        self.assertEqual(caught.exception.code, "provider_request_limit")
        self.assertEqual(_SpeechServer.calls, [])

    def test_invalid_response_status_and_geometry_are_rejected(self):
        for status, code in ((401, "provider_auth_failed"), (429, "provider_rate_limited"),
                             (500, "provider_unavailable")):
            with self.subTest(status=status):
                _SpeechServer.status = status
                _SpeechServer.response = b"secret"
                with self.assertRaises(AzureSpeechError) as caught:
                    self.provider.transcribe(self.request)
                self.assertEqual(caught.exception.code, code)
                self.assertNotIn("secret", str(caught.exception))
        _SpeechServer.status = 200
        _SpeechServer.response = {"durationMilliseconds": 2000, "phrases": [{
            "offsetMilliseconds": 0, "durationMilliseconds": 10, "text": "x",
            "words": [{"offsetMilliseconds": 0, "durationMilliseconds": 20, "text": "x"}],
        }]}
        with self.assertRaises(AzureSpeechError) as caught:
            self.provider.transcribe(self.request)
        self.assertEqual(caught.exception.code, "provider_invalid_response")


if __name__ == "__main__":
    unittest.main()
