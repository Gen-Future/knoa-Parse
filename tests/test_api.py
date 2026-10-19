import tempfile
import unittest
from pathlib import Path
import sys
import importlib.util

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

API_AVAILABLE = importlib.util.find_spec("fastapi") is not None
if API_AVAILABLE:
    from fastapi.testclient import TestClient
    from knoa_parse.apps.api import create_app
from knoa_parse.apps.worker import run_once
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store


@unittest.skipUnless(API_AVAILABLE, "Install the optional api group to run HTTP tests")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(Path(self.temp.name), max_source_bytes=64)
        self.client = TestClient(create_app(self.settings, "test-token"))
        self.auth = {"Authorization": "Bearer test-token"}

    def test_api_upload_queue_worker_and_result(self):
        upload = self.client.post("/v1/sources?filename=hello.txt", content="你好😀".encode(), headers=self.auth)
        self.assertEqual(upload.status_code, 201)
        queued = self.client.post("/v1/jobs", json={"source_id": upload.json()["id"], "idempotency_key": "one"}, headers=self.auth)
        self.assertEqual(queued.status_code, 202)
        job_id = queued.json()["id"]
        self.assertEqual(self.client.get(f"/v1/jobs/{job_id}/result", headers=self.auth).status_code, 409)
        run_once(Store(self.settings), job_id)
        result = self.client.get(f"/v1/jobs/{job_id}/result", headers=self.auth)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["blocks"][0]["text"], "你好😀")
        artifact_id = result.json()["artifacts"][0]["id"]
        self.assertEqual(self.client.get(f"/v1/artifacts/{artifact_id}", headers=self.auth).content, "你好😀".encode())

    def test_token_required_for_source_results_and_capabilities(self):
        self.assertEqual(self.client.get("/v1/capabilities").status_code, 401)
        self.assertEqual(self.client.get("/v1/artifacts/unknown").status_code, 401)
        self.assertEqual(self.client.get("/v1/jobs/unknown/result").status_code, 401)

    def test_unknown_fields_and_untrusted_paths_are_not_job_options(self):
        response = self.client.post("/v1/jobs", json={"source_id": "x", "path": "/etc/passwd"}, headers=self.auth)
        self.assertEqual(response.status_code, 422)

    def test_streaming_upload_limit_and_cleanup(self):
        response = self.client.post("/v1/sources?filename=large.txt", content=b"x" * 65, headers=self.auth)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(list((Path(self.temp.name) / "staging").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
