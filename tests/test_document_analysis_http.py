import base64
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from knoa_parse.core.document_analysis import PageAnalysis, PageRequest
from knoa_parse.core.errors import ParseError
from knoa_parse.enrichment.document import analyze_pages
from knoa_parse.providers.document_analysis.http import (
    DocumentProviderError, HttpDocumentAnalysisConfig, HttpDocumentAnalysisProvider,
)
from m3_fixtures import ScriptedDocumentProvider, fixture


class _Server(BaseHTTPRequestHandler):
    response = {"page": 1, "model": "remote-test", "elements": [{
        "kind": "text", "text": "远端合成结果", "bbox": [0.1, 0.2, 0.5, 0.4],
        "unit": "normalized", "origin": "top_left",
    }]}
    status = 200
    headers = {"Content-Type": "application/json"}
    received = []
    redirect = None
    status_by_page = None

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.__class__.received.append((self.path, dict(self.headers), body))
        if self.redirect:
            self.send_response(307)
            self.send_header("Location", self.redirect)
            self.end_headers()
            return
        raw = self.response if isinstance(self.response, bytes) else json.dumps(self.response).encode()
        status = self.status
        if self.status_by_page is not None:
            try:
                status = self.status_by_page.get(json.loads(body).get("page"), status)
            except (ValueError, TypeError):
                pass
        self.send_response(status)
        for key, value in self.headers.items():
            pass
        for key, value in self.__class__.headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        pass


class HttpProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Server)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def setUp(self):
        self.native, self.pages = fixture()
        self._Server = _Server
        _Server.received.clear()
        _Server.response = {"page": 1, "model": "remote-test", "elements": [{
            "kind": "text", "text": "远端合成结果", "bbox": [0.1, 0.2, 0.5, 0.4],
            "unit": "normalized", "origin": "top_left",
        }]}
        _Server.status = 200
        _Server.headers = {"Content-Type": "application/json"}
        _Server.redirect = None
        _Server.status_by_page = None
        base = f"http://127.0.0.1:{self.server.server_port}"
        self.provider = HttpDocumentAnalysisProvider(HttpDocumentAnalysisConfig(
            provider="test-remote", base_url=base, api_key="synthetic-secret",
            allow_local_http=True, max_response_bytes=4096,
        ))
        self.request = PageRequest(page=self.pages[0], context=[], timeout_seconds=5, trace_id="trace-test")

    def test_request_mapping_and_non_sensitive_capability(self):
        response = self.provider.analyze_page(self.request)
        self.assertEqual(response.page, 1)
        self.assertEqual(len(_Server.received), 1)
        path, headers, raw = _Server.received[0]
        self.assertEqual(path, "/analyze/page")
        self.assertEqual(headers["Authorization"], "Bearer synthetic-secret")
        payload = json.loads(raw)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(base64.b64decode(payload["image_base64"]), self.pages[0].content)
        self.assertNotIn("source-synthetic", raw.decode())
        description = self.provider.describe().model_dump_json()
        self.assertNotIn("synthetic-secret", description)

    def test_https_is_default_and_only_explicit_local_http_is_allowed(self):
        with self.assertRaises(ValueError):
            HttpDocumentAnalysisConfig(provider="x", base_url="http://example.com", api_key="x")
        with self.assertRaises(ValueError):
            HttpDocumentAnalysisConfig(provider="x", base_url="https://example.com/a?secret=x", api_key="x")

    def test_status_errors_are_stable_and_body_is_not_exposed(self):
        for status, code, retryable in ((401, "provider_auth_failed", False), (402, "provider_billing_required", False),
                                        (404, "provider_not_found", False), (408, "provider_timeout", True),
                                        (429, "provider_rate_limited", True), (500, "provider_unavailable", True),
                                        (400, "provider_invalid_request", False)):
            with self.subTest(status=status):
                _Server.status = status
                _Server.response = b"secret-provider-error-body"
                with self.assertRaises(DocumentProviderError) as caught:
                    self.provider.analyze_page(self.request)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn("secret-provider", str(caught.exception))

    def test_redirect_is_rejected_without_sending_second_request(self):
        _Server.redirect = "/other"
        with self.assertRaises(DocumentProviderError) as caught:
            self.provider.analyze_page(self.request)
        self.assertEqual(caught.exception.code, "provider_redirect")
        self.assertEqual(len(_Server.received), 1)

    def test_response_limits_and_invalid_json(self):
        _Server.response = b"x" * 4097
        with self.assertRaises(DocumentProviderError) as caught:
            self.provider.analyze_page(self.request)
        self.assertEqual(caught.exception.code, "provider_response_limit")
        _Server.response = b"not-json"
        with self.assertRaises(DocumentProviderError) as caught:
            self.provider.analyze_page(self.request)
        self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_provider_response_is_strictly_validated(self):
        for response in (
            {"page": 2, "model": "x", "elements": []},
            {"page": 1, "model": "x", "elements": [], "blank": False},
            {"page": 1, "model": "x", "elements": [{"text": "x", "bbox": [0, 0, 0, 2], "unit": "px", "origin": "top_left"}]},
            {"page": 1, "model": "x", "elements": [{"text": "x", "bbox": [0, 0, 1, 1], "unit": "mm", "origin": "top_left"}]},
        ):
            with self.subTest(response=response):
                _Server.response = response
                with self.assertRaises(DocumentProviderError) as caught:
                    self.provider.analyze_page(self.request)
                self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_timeout_or_unavailable_is_retryable_and_single_attempt(self):
        provider = HttpDocumentAnalysisProvider(HttpDocumentAnalysisConfig(
            provider="test-remote", base_url="http://127.0.0.1:1", api_key="synthetic-secret",
            allow_local_http=True, timeout_seconds=0.1,
        ))
        with self.assertRaises(DocumentProviderError) as caught:
            provider.analyze_page(self.request)
        self.assertTrue(caught.exception.retryable)

    def test_adapter_never_promotes_result_to_parse_result(self):
        response = self.provider.analyze_page(self.request)
        self.assertIsInstance(response, PageAnalysis)
        self.assertNotIsInstance(response, ParseError)

    def test_adapter_errors_preserve_m3_page_partial_semantics(self):
        _Server.status_by_page = {1: 200, 2: 500}
        partial = analyze_pages(self.native, self.pages, self.provider, dry_run=False)
        self.assertEqual(partial.status, "partial")
        self.assertEqual(partial.outcomes[0].status, "completed")
        self.assertEqual(partial.outcomes[1].status, "failed")
        self.assertEqual(partial.outcomes[1].code, "provider_unavailable")
        self.assertTrue(partial.invocations[1].retryable)
        self.assertEqual(len(_Server.received), 2)


if __name__ == "__main__":
    unittest.main()
