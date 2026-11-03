import sqlite3
import tempfile
import unittest
import gc
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.provider_runs import InvocationRecord, ProviderJobRef
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store


def make_record(**changes):
    value = {
        "id": "inv-1", "run_id": "run-1", "unit_id": "page-1", "provider": "remote",
        "operation": "document_analysis", "config_fingerprint": "a" * 64,
        "request_fingerprint": "b" * 64,
    }
    value.update(changes)
    return InvocationRecord.model_validate(value)


class ProviderStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Settings(Path(self.temp.name)))

    def tearDown(self):
        self.temp.cleanup()

    def test_schema_version_and_old_database_migrate_idempotently(self):
        legacy = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        migrated = None
        migrated_again = None
        try:
            path = Path(legacy.name) / "tasks.sqlite3"
            with sqlite3.connect(path) as db:
                db.executescript("""
                    CREATE TABLE sources(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                    CREATE TABLE jobs(id TEXT PRIMARY KEY, source_id TEXT NOT NULL, state TEXT NOT NULL,
                                      target TEXT NOT NULL, request_key TEXT UNIQUE, token TEXT,
                                      lease_until REAL, error TEXT, result_id TEXT, created REAL NOT NULL);
                    CREATE TABLE artifacts(id TEXT PRIMARY KEY, digest TEXT NOT NULL, media_type TEXT NOT NULL,
                                           size_bytes INTEGER NOT NULL);
                """)
            migrated = Store(Settings(Path(legacy.name)))
            with migrated.connection() as db:
                self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE name='provider_invocations'").fetchone()[0], "provider_invocations")
            self.assertEqual(migrated.invocation_schema_version(), 2)
            migrated_again = Store(Settings(Path(legacy.name)))
            self.assertEqual(migrated.invocation_schema_version(), 2)
        finally:
            del migrated_again
            del migrated
            gc.collect()
            legacy.cleanup()

    def test_round_trip_and_read_only_access(self):
        item = make_record()
        self.assertEqual(self.store.save_invocation(item), item)
        self.assertEqual(self.store.invocation(item.id), item)
        read_only = Store(Settings(Path(self.temp.name)), read_only=True)
        self.assertEqual(read_only.invocation(item.id), item)
        with self.assertRaises(ParseError) as caught:
            read_only.save_invocation(make_record(id="inv-2", unit_id="page-2"))
        self.assertEqual(caught.exception.code, "read_only")

    def test_same_body_is_idempotent_and_identity_conflicts_are_visible(self):
        item = make_record()
        self.store.save_invocation(item)
        self.assertEqual(self.store.save_invocation(item), item)
        with self.assertRaises(ParseError) as caught:
            self.store.save_invocation(item.model_copy(update={"provider": "other"}))
        self.assertEqual(caught.exception.code, "invocation_conflict")
        with self.assertRaises(ParseError) as caught:
            self.store.save_invocation(make_record(id="inv-2"))
        self.assertEqual(caught.exception.code, "invocation_conflict")

    def test_expected_state_and_legal_transitions(self):
        planned = make_record()
        self.store.save_invocation(planned)
        submitted = planned.model_copy(update={"state": "submitted", "attempt": 1, "billing_state": "pending",
                                               "provider_job": ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg")})
        self.store.save_invocation(submitted, expected_state="planned")
        unknown = submitted.model_copy(update={"state": "unknown", "billing_state": "unknown", "error_code": "timeout"})
        self.store.save_invocation(unknown, expected_state="submitted")
        succeeded = unknown.model_copy(update={"state": "succeeded", "billing_state": "unknown", "error_code": None,
                                               "response_artifact_id": "artifact-1"})
        self.store.save_invocation(succeeded, expected_state="unknown")
        self.assertEqual(self.store.invocation(planned.id).state, "succeeded")
        with self.assertRaises(ParseError):
            self.store.save_invocation(submitted, expected_state="succeeded")
        with self.assertRaises(ParseError):
            self.store.save_invocation(succeeded.model_copy(update={"state": "submitted", "attempt": 2,
                                                                    "billing_state": "pending", "response_artifact_id": None}),
                                       expected_state="succeeded")

    def test_failed_retry_requires_next_attempt_and_billing_does_not_move_back(self):
        failed = make_record(state="failed", attempt=1, billing_state="known", retryable=True, error_code="rate_limit",
                             provider_job=ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg",
                                                         idempotency_supported=True))
        self.store.save_invocation(failed)
        retry = failed.model_copy(update={"state": "submitted", "attempt": 2, "billing_state": "pending", "error_code": None})
        self.store.save_invocation(retry, expected_state="failed")
        with self.assertRaises(ParseError):
            self.store.save_invocation(retry.model_copy(update={"state": "failed", "attempt": 1,
                                                                "billing_state": "known", "error_code": "again"}),
                                       expected_state="submitted")

    def test_list_filters_and_missing_records(self):
        self.store.save_invocation(make_record(id="inv-2", unit_id="page-2"))
        self.store.save_invocation(make_record(id="inv-1", unit_id="page-1"))
        other = make_record(id="inv-3", run_id="run-2", unit_id="page-1")
        self.store.save_invocation(other)
        self.assertEqual([item.id for item in self.store.list_invocations("run-1")], ["inv-1", "inv-2"])
        self.assertEqual(self.store.list_invocations("run-1", "planned")[0].id, "inv-1")
        with self.assertRaises(ParseError) as caught:
            self.store.invocation("missing")
        self.assertEqual(caught.exception.code, "invocation_not_found")

    def test_concurrent_same_unit_has_one_winner(self):
        records = [make_record(id="inv-a"), make_record(id="inv-b")]

        def write(item):
            try:
                Store(Settings(Path(self.temp.name))).save_invocation(item)
                return "ok"
            except ParseError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write, records))
        self.assertEqual(results.count("ok"), 1)
        self.assertEqual(results.count("invocation_conflict"), 1)
        self.assertEqual(len(self.store.list_invocations("run-1")), 1)


if __name__ == "__main__":
    unittest.main()
