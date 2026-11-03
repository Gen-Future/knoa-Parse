"""Optional console composition and general-purpose read-only observation endpoints."""
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store

API_AVAILABLE = importlib.util.find_spec("fastapi") is not None
if API_AVAILABLE:
    from fastapi.testclient import TestClient
    from knoa_parse.apps.api import create_app
    from knoa_parse.apps.console import create_app as create_console


@unittest.skipUnless(API_AVAILABLE, "Install api for the optional console")
class ConsoleTests(unittest.TestCase):
    def test_demo_opens_without_login_and_runs_source_job_flow(self):
        from knoa_parse.apps.worker import run_once
        client = TestClient(create_console(create_app(self.settings)))
        page = client.get("/")
        self.assertNotIn('id="connection-dialog"', page.text)
        self.assertNotIn('id="api-token"', page.text)
        self.assertEqual(client.get("/api/v1/capabilities").status_code, 200)
        self.assertEqual(client.get("/api/v1/jobs").status_code, 200)
        source = client.post("/api/v1/sources?filename=demo.txt", content=b"single user demo").json()
        job = client.post("/api/v1/jobs", json={"source_id": source["id"]}).json()
        run_once(self.store, job["id"])
        result = client.get(f"/api/v1/jobs/{job['id']}/result")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["blocks"][0]["text"], "single user demo")
        self.assertEqual(client.get(f"/api/v1/artifacts/{source['id']}").content, b"single user demo")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings = Settings(Path(self.temp.name))
        self.store = Store(self.settings)
        self.api = create_app(self.settings, "console-test")
        self.client = TestClient(create_console(self.api))
        self.auth = {"Authorization": "Bearer console-test"}

    def test_public_shell_never_bypasses_api_authentication(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("console-test", page.text)
        self.assertIn("default-src 'self'", page.headers["content-security-policy"])
        for path in ("/api/v1/capabilities", "/api/v1/jobs", "/api/v1/sources/unknown", "/api/v1/artifacts/unknown"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get("/api/v1/capabilities", headers=self.auth).status_code, 200)
        self.assertIn(self.client.get("/model.mjs").headers["content-type"].split(";")[0],
                      ("text/javascript", "application/javascript"))

    def test_recent_jobs_include_cli_jobs_without_claiming_or_exposing_lease(self):
        source = self.store.ingest(io.BytesIO(b"hello"), "outside-browser.txt")
        jobs = [self.store.create_job(source.id) for _ in range(3)]
        with self.store.connection() as db:
            for index, job in enumerate(jobs):
                db.execute("UPDATE jobs SET created=? WHERE id=?", (index, job["id"]))
        self.store.claim(jobs[0]["id"])
        response = self.client.get("/api/v1/jobs?limit=2", headers=self.auth)
        self.assertEqual(response.status_code, 200)
        listing = response.json()
        self.assertTrue(listing["has_more"])
        self.assertEqual([job["id"] for job in listing["items"]], [jobs[2]["id"], jobs[1]["id"]])
        self.assertEqual(listing["items"][0]["source"]["filename"], "outside-browser.txt")
        self.assertEqual(listing["items"][0]["created_at"], 2)
        for job in listing["items"]:
            self.assertFalse({"token", "lease_until", "request_key", "path"} & set(job))
        self.assertEqual(self.store.job(jobs[0]["id"])["state"], "running")
        self.assertEqual(self.store.job(jobs[1]["id"])["state"], "queued")
        self.assertEqual(self.client.get(f"/api/v1/sources/{source.id}", headers=self.auth).json()["sha256"], source.sha256)

    def test_observation_limits_are_bounded_and_not_ui_required(self):
        for limit in (0, 101, -1):
            with self.subTest(limit=limit):
                self.assertEqual(self.client.get(f"/api/v1/jobs?limit={limit}", headers=self.auth).status_code, 422)
        plain = TestClient(self.api)
        self.assertEqual(plain.get("/v1/jobs", headers=self.auth).json()["items"], [])
        self.assertEqual(plain.get("/style.css").status_code, 404)

    def test_console_upload_uses_original_queue_and_limits(self):
        upload = self.client.post("/api/v1/sources?filename=evidence.txt", content=b"raw source", headers=self.auth)
        self.assertEqual(upload.status_code, 201)
        queued = self.client.post("/api/v1/jobs", json={"source_id": upload.json()["id"]}, headers=self.auth)
        self.assertEqual(queued.status_code, 202)
        self.assertEqual(queued.json()["state"], "queued")
        self.assertEqual(self.client.get(f"/api/v1/jobs/{queued.json()['id']}/result", headers=self.auth).status_code, 409)
        self.assertEqual(self.client.get("/../AGENTS.md").status_code, 404)


if __name__ == "__main__":
    unittest.main()
