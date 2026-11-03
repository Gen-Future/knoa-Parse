import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from knoa_parse.apps.worker import run_once
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import ParseResult
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Settings(Path(self.temp.name)))

    def source(self, raw=b"hello", filename="test.txt"):
        return self.store.ingest(io.BytesIO(raw), filename)

    def test_unicode_bom_crlf_offsets_survive_worker_and_persistence(self):
        text = "\ufeff中文\r\n😀\nend"
        source = self.source(text.encode())
        job = self.store.create_job(source.id)
        self.assertTrue(run_once(self.store, job["id"]))
        reopened = Store(self.store.settings)
        self.assertEqual(reopened.job(job["id"])["state"], "succeeded")
        result = reopened.result(job["id"])
        block = result.blocks[0]
        self.assertEqual(block.text, text)
        self.assertEqual(text[block.locators[0].start:block.locators[0].end], block.text)
        self.assertEqual(result.source.sha256, source.sha256)

    def test_cli_json_is_utf8_under_legacy_output_encoding(self):
        text = "中文😀\r\n原文"
        path = Path(self.temp.name) / "中文😀.txt"
        path.write_bytes(text.encode("utf-8"))
        completed = subprocess.run(
            [sys.executable, "-m", "knoa_parse", "--data-dir", str(self.store.root), "parse", str(path)],
            env=dict(os.environ, PYTHONIOENCODING="gbk", PYTHONUTF8="0"),
            capture_output=True, timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8"))
        result = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(result["blocks"][0]["text"], text)
        self.assertEqual(result["source"]["filename"], path.name)

    def test_worker_output_budget_rejects_result_before_publication(self):
        self.store = Store(Settings(Path(self.temp.name), max_result_bytes=512))
        job = self.store.create_job(self.source(b"x" * 4096).id)
        run_once(self.store, job["id"])
        state = self.store.job(job["id"])
        self.assertEqual(state["state"], "failed")
        self.assertEqual(state["error"]["code"], "resource_limit")
        self.assertIsNone(state["result_artifact_id"])
        self.assertEqual(list((self.store.root / "staging").iterdir()), [])

    def test_json_native_types_and_scalar_root(self):
        for value in ({"中文": [1, False, None]}, ["x"], 123, "text", False, None):
            with self.subTest(value=value):
                source = self.source(json.dumps(value).encode(), "test.json")
                job = self.store.create_job(source.id)
                run_once(self.store, job["id"])
                block = self.store.result(job["id"]).blocks[0]
                self.assertEqual(block.data["value"], value)
                self.assertEqual(block.locators[0].pointer, "")

    def test_empty_text_can_complete_without_fabricated_evidence(self):
        job = self.store.create_job(self.source(b"").id)
        run_once(self.store, job["id"])
        self.assertEqual(self.store.result(job["id"]).blocks, [])

    def test_bad_json_is_rejected_before_task_creation(self):
        for raw in (b'{"a":1,"a":2}', b'NaN', b'1e999', b'{', b'[' * 70 + b'0' + b']' * 70):
            with self.subTest(raw=raw), self.assertRaises(ParseError):
                self.source(raw, "bad.json")

    def test_binary_and_signature_conflicts_are_not_text(self):
        for raw, name in ((b'\0abc', "a.txt"), (b'%PDF-1.7', "a.txt"), (b'word', "a.docx")):
            with self.subTest(name=name), self.assertRaises(ParseError):
                self.source(raw, name)
        self.assertEqual(self.source(b"PK is plain text").media_type, "text/plain")

    def test_size_limit_cleans_staging(self):
        store = Store(Settings(Path(self.temp.name), max_source_bytes=3))
        with self.assertRaises(ParseError) as caught:
            store.ingest(io.BytesIO(b"four"), "a.txt")
        self.assertEqual(caught.exception.code, "resource_limit")
        self.assertEqual(list((store.root / "staging").iterdir()), [])

    def test_idempotency_and_conflicts(self):
        source = self.source()
        first = self.store.create_job(source.id, request_key="same")
        self.assertEqual(first, self.store.create_job(source.id, request_key="same"))
        with self.assertRaises(ParseError) as caught:
            self.store.create_job(self.source(b"other").id, request_key="same")
        self.assertEqual(caught.exception.status_code, 409)

    def test_two_workers_cannot_claim_same_job(self):
        self.store.create_job(self.source().id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: self.store.claim(), range(2)))
        self.assertEqual(sum(c is not None for c in claims), 1)

    def test_queued_cancellation_prevents_execution(self):
        job = self.store.create_job(self.source().id)
        self.store.cancel(job["id"])
        self.assertFalse(run_once(self.store, job["id"]))
        with self.assertRaises(ParseError):
            self.store.result(job["id"])

    def test_original_digest_checked_in_child(self):
        source = self.source()
        job = self.store.create_job(source.id)
        self.store.blob_path(source.sha256).write_bytes(b"evil!")
        run_once(self.store, job["id"])
        self.assertEqual(self.store.job(job["id"])["state"], "failed")
        with self.assertRaises(ParseError):
            self.store.result(job["id"])

    def test_expired_lease_fails_without_automatic_retry(self):
        job = self.store.create_job(self.source().id)
        self.store.claim()
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET lease_until=0 WHERE id=?", (job["id"],))
        self.assertIsNone(self.store.claim())
        self.assertEqual(self.store.job(job["id"])["error"]["code"], "worker_lost")

    def test_stale_worker_cannot_publish_after_cancellation(self):
        from knoa_parse.parsers.text.parser import TextParser

        source = self.source()
        job = self.store.create_job(source.id)
        _, token = self.store.claim()
        self.store.cancel(job["id"])
        self.store.finish(job["id"], token, TextParser().parse(source, self.store.verify_source(source)))
        self.assertIsNone(self.store.job(job["id"])["result_artifact_id"])

    def test_missing_external_capability_fails_preflight(self):
        with self.assertRaises(ParseError) as caught:
            self.store.create_job(self.source().id, "document_understanding")
        self.assertEqual(caught.exception.code, "capability_missing")

    def test_docling_stays_disabled(self):
        from knoa_parse.apps.runtime import capabilities

        source = self.source(b"%PDF-1.7\n", "a.pdf")
        with self.assertRaises(ParseError) as caught:
            self.store.create_job(source.id)
        self.assertEqual(caught.exception.code, "engine_not_enabled")
        with patch("knoa_parse.apps.runtime.dependency_status", return_value={"passed": False}):
            self.assertFalse(capabilities()["document_engine"]["enabled"])

    def test_result_digest_is_verified(self):
        job = self.store.create_job(self.source().id)
        run_once(self.store, job["id"])
        path, _ = self.store.artifact(self.store.job(job["id"])["result_artifact_id"])
        path.write_bytes(b"corrupt")
        with self.assertRaises(ParseError) as caught:
            self.store.result(job["id"])
        self.assertEqual(caught.exception.code, "artifact_corrupt")

    def test_runtime_semantics_reject_invalid_references_and_status(self):
        job = self.store.create_job(self.source().id)
        run_once(self.store, job["id"])
        value = self.store.result(job["id"]).model_dump(mode="json")
        invalid = copy.deepcopy(value)
        invalid["blocks"][0]["locators"][0]["artifact_id"] = "missing"
        with self.assertRaises(ValueError):
            ParseResult.model_validate(invalid)
        invalid = copy.deepcopy(value)
        del invalid["schema_version"]
        with self.assertRaises(ValueError):
            ParseResult.model_validate(invalid)
        invalid = copy.deepcopy(value)
        invalid["issues"] = [{"code": "lost", "message": "lost", "severity": "error"}]
        with self.assertRaises(ValueError):
            ParseResult.model_validate(invalid)

    def test_corrupt_staged_artifact_cannot_be_published(self):
        from knoa_parse.core.artifacts import StagedArtifacts
        from knoa_parse.parsers.text.parser import TextParser

        source = self.source()
        job = self.store.create_job(source.id)
        _, token = self.store.claim(job["id"])
        stage = Path(self.temp.name) / "artifacts"
        artifact = StagedArtifacts(stage, 1024).put(b"{}", "engine_result", "application/json")
        result = TextParser().parse(source, self.store.verify_source(source))
        result.artifacts.append(artifact)
        (stage / artifact.sha256).write_bytes(b"[]")
        with self.assertRaises(ParseError) as caught:
            self.store.finish(job["id"], token, result, stage)
        self.assertEqual(caught.exception.code, "artifact_corrupt")
        with self.assertRaises(ParseError):
            self.store.artifact(artifact.id)

    def test_task_local_artifact_budget_is_cumulative(self):
        from knoa_parse.core.artifacts import StagedArtifacts

        sink = StagedArtifacts(Path(self.temp.name) / "limited", 5)
        sink.put(b"one", "derived", "image/png")
        with self.assertRaises(ParseError) as caught:
            sink.put(b"two", "derived", "image/png")
        self.assertEqual(caught.exception.code, "resource_limit")

    def _slow_child(self, *args, **kwargs):
        self.slow_process = self.real_popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           start_new_session=os.name != "nt")
        return self.slow_process

    def test_timeout_terminates_child_and_fails(self):
        self.store = Store(Settings(Path(self.temp.name), job_timeout_seconds=0.1))
        job = self.store.create_job(self.source().id)
        self.real_popen = subprocess.Popen
        with patch("knoa_parse.apps.worker.subprocess.Popen", self._slow_child):
            run_once(self.store, job["id"])
        self.assertEqual(self.store.job(job["id"])["error"]["code"], "execution_timeout")
        self.assertIsNotNone(self.slow_process.poll())

    def test_running_cancellation_stops_child(self):
        job = self.store.create_job(self.source().id)
        self.real_popen = subprocess.Popen
        with patch("knoa_parse.apps.worker.subprocess.Popen", self._slow_child):
            runner = threading.Thread(target=run_once, args=(self.store, job["id"]))
            runner.start()
            deadline = time.monotonic() + 3
            while self.store.job(job["id"])["state"] != "running" and time.monotonic() < deadline:
                time.sleep(0.01)
            self.store.cancel(job["id"])
            runner.join(timeout=3)
            self.assertFalse(runner.is_alive())
        self.assertEqual(self.store.job(job["id"])["state"], "cancelled")
        self.assertIsNotNone(self.slow_process.poll())


if __name__ == "__main__":
    unittest.main()
