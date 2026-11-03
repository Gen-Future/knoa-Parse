import base64
import hashlib
import json
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))

from knoa_parse.core.document_analysis import PageRequest
from knoa_parse.providers.document_analysis.azure import (
    AzureDocumentAnalysisConfig,
    AzureDocumentAnalysisProvider,
    AzureDocumentProviderError,
)
from m3_fixtures import fixture


class _AzureServer(BaseHTTPRequestHandler):
    calls = []
    post_status = 202
    post_location = None
    post_body = None
    poll_payloads = []
    poll_status = 200
    poll_retry_after = None
    redirect = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.__class__.post_body = self.rfile.read(length)
        self.__class__.calls.append(("POST", self.path, dict(self.headers)))
        if self.redirect:
            self.send_response(307)
            self.send_header("Location", self.redirect)
            self.end_headers()
            return
        self.send_response(self.post_status)
        if self.post_location:
            self.send_header("Operation-Location", self.post_location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self.__class__.calls.append(("GET", self.path, dict(self.headers)))
        payload = self.__class__.poll_payloads.pop(0) if self.__class__.poll_payloads else {"status": "running"}
        raw = json.dumps(payload).encode()
        self.send_response(self.poll_status)
        self.send_header("Content-Type", "application/json")
        if self.poll_retry_after is not None:
            self.send_header("Retry-After", str(self.poll_retry_after))
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, format, *args):
        pass


class AzureAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _AzureServer)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=2)
        cls.server.server_close()

    def setUp(self):
        _AzureServer.calls.clear()
        _AzureServer.post_status = 202
        _AzureServer.post_location = f"http://127.0.0.1:{self.server.server_port}/operations/job-42?api-version=2024-11-30"
        _AzureServer.post_body = None
        _AzureServer.poll_payloads = [{
            "status": "succeeded",
            "analyzeResult": {"pages": [{
                "pageNumber": 1, "width": 1200, "height": 1600, "unit": "pixel",
                "lines": [{"content": "Azure 结果", "polygon": [10, 20, 300, 20, 300, 60, 10, 60]}],
            }]},
        }]
        _AzureServer.poll_status = 200
        _AzureServer.poll_retry_after = None
        _AzureServer.redirect = None
        self.native, pages = fixture()
        self.page = pages[0]
        self.request = PageRequest(page=self.page, context=[], timeout_seconds=2, trace_id="azure-test")
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.provider = AzureDocumentAnalysisProvider(AzureDocumentAnalysisConfig(
            endpoint=self.base, api_key="synthetic-secret", allow_local_http=True,
            poll_interval_seconds=0.01, max_poll_interval_seconds=0.02, max_response_bytes=4096,
        ))

    def test_submit_poll_maps_single_page_and_keeps_remote_job(self):
        result = self.provider.poll_page(self.provider.submit_page(self.request), self.request)
        self.assertEqual(result.operation.remote_job_id, "job-42")
        self.assertEqual(result.analysis.page, 1)
        self.assertEqual(result.analysis.elements[0].text, "Azure 结果")
        self.assertEqual(result.analysis.elements[0].bbox, [10.0, 20.0, 300.0, 60.0])
        method, path, headers = _AzureServer.calls[0]
        self.assertEqual(method, "POST")
        self.assertIn("/documentintelligence/documentModels/prebuilt-layout:analyze", path)
        self.assertIn("api-version=2024-11-30", path)
        self.assertEqual(headers["Ocp-Apim-Subscription-Key"], "synthetic-secret")
        body = json.loads(_AzureServer.post_body)
        self.assertEqual(base64.b64decode(body["base64Source"]), self.page.content)
        self.assertEqual(_AzureServer.calls[1][0], "GET")

    def test_analyze_page_is_the_protocol_entrypoint(self):
        analysis = self.provider.analyze_page(self.request)
        self.assertEqual(analysis.model, "prebuilt-layout@2024-11-30")
        self.assertNotIn("synthetic-secret", analysis.model)

    def test_capability_is_external_and_non_sensitive(self):
        capability = self.provider.describe()
        self.assertEqual(capability.execution, "external_service")
        self.assertEqual(capability.coordinate_units, ["px"])
        self.assertNotIn("synthetic-secret", capability.model_dump_json())

    def test_config_rejects_non_https_and_bad_model(self):
        with self.assertRaises(ValueError):
            AzureDocumentAnalysisConfig(endpoint="https://example.com?secret=x", api_key="x")
        with self.assertRaises(ValueError):
            AzureDocumentAnalysisConfig(endpoint="http://example.com", api_key="x")
        with self.assertRaises(ValueError):
            AzureDocumentAnalysisConfig(endpoint=self.base, api_key="x", allow_local_http=True, model_id="bad/id")

    def test_retry_after_is_capped_and_intermediate_statuses_are_polled(self):
        _AzureServer.poll_payloads = [{"status": "running"}, {"status": "succeeded", "analyzeResult": {
            "pages": [{"pageNumber": 1, "width": 1200, "height": 1600, "unit": "pixel", "lines": []}]
        }}]
        _AzureServer.poll_retry_after = 5
        result = self.provider.analyze_page(self.request)
        self.assertTrue(result.blank)
        self.assertEqual(sum(call[0] == "GET" for call in _AzureServer.calls), 2)

    def test_timeout_retains_operation_and_is_not_safe_to_retry(self):
        _AzureServer.poll_payloads = [{"status": "running"}]
        request = self.request.model_copy(update={"timeout_seconds": 0.1})
        with self.assertRaises(AzureDocumentProviderError) as caught:
            self.provider.analyze_page(request)
        self.assertEqual(caught.exception.code, "provider_timeout")
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(caught.exception.operation.remote_job_id, "job-42")

    def test_failed_and_cancelled_operations_are_stable(self):
        for status, code in (("failed", "provider_remote_failed"), ("cancelled", "provider_remote_cancelled")):
            with self.subTest(status=status):
                _AzureServer.poll_payloads = [{"status": status}]
                with self.assertRaises(AzureDocumentProviderError) as caught:
                    self.provider.analyze_page(self.request)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.operation.remote_job_id, "job-42")

    def test_operation_location_must_stay_on_configured_resource(self):
        _AzureServer.post_location = "https://evil.example/operations/job-42"
        with self.assertRaises(AzureDocumentProviderError) as caught:
            self.provider.submit_page(self.request)
        self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_structured_output_and_invalid_geometry_are_rejected(self):
        cases = [
            {"tables": [{}]},
            {"lines": [{"content": "x", "polygon": [0, 0, 1201, 0, 1201, 1, 0, 1]}]},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                page = {"pageNumber": 1, "width": 1200, "height": 1600, "unit": "pixel", "lines": []}
                result = {"pages": [page]}
                if "tables" in extra:
                    result["tables"] = extra["tables"]
                else:
                    page.update(extra)
                _AzureServer.poll_payloads = [{"status": "succeeded", "analyzeResult": result}]
                with self.assertRaises(AzureDocumentProviderError) as caught:
                    self.provider.analyze_page(self.request)
                self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_duplicate_json_or_wrong_dimensions_are_rejected(self):
        _AzureServer.poll_payloads = [{"status": "succeeded", "analyzeResult": {"pages": [{
            "pageNumber": 1, "width": 1000, "height": 1600, "unit": "pixel", "lines": []
        }]}}]
        with self.assertRaises(AzureDocumentProviderError) as caught:
            self.provider.analyze_page(self.request)
        self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_submit_status_and_redirect_are_rejected_without_following(self):
        _AzureServer.post_status = 500
        with self.assertRaises(AzureDocumentProviderError) as caught:
            self.provider.submit_page(self.request)
        self.assertEqual(caught.exception.code, "provider_unavailable")
        _AzureServer.calls.clear()
        _AzureServer.post_status = 202
        _AzureServer.redirect = "/other"
        with self.assertRaises(AzureDocumentProviderError) as caught:
            self.provider.submit_page(self.request)
        self.assertEqual(caught.exception.code, "provider_redirect")
        self.assertEqual(len(_AzureServer.calls), 1)


if __name__ == "__main__":
    unittest.main()
