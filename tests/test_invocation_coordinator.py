import tempfile
import unittest
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.provider_runs import ProviderJobRef, ProviderUsage
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store
from knoa_parse.enrichment.invocations import InvocationCoordinator, InvocationUnit


class InvocationCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Settings(Path(self.temp.name)))
        self.coordinator = InvocationCoordinator(self.store, "run-1", "remote", "document_analysis", "a" * 64)
        self.units = [InvocationUnit(unit_id="page-1", request_fingerprint="1" * 64),
                      InvocationUnit(unit_id="page-2", request_fingerprint="2" * 64)]

    def tearDown(self):
        self.temp.cleanup()

    def test_plan_is_atomic_and_idempotent(self):
        planned = self.coordinator.plan(self.units)
        self.assertEqual([record.unit_id for record in planned], ["page-1", "page-2"])
        self.assertEqual(self.coordinator.plan(self.units), planned)
        with self.assertRaises(ParseError):
            self.coordinator.plan([self.units[0], self.units[0]])
        self.assertEqual(len(self.store.list_invocations("run-1")), 2)

    def test_lifecycle_persists_and_recovery_is_explicit(self):
        self.coordinator.plan(self.units)
        job = ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg", query_supported=True,
                             idempotency_supported=True)
        submitted = self.coordinator.submit("page-1", job)
        self.assertEqual(submitted.attempt, 1)
        unknown = self.coordinator.unknown("page-1", "timeout", job)
        self.assertEqual(self.coordinator.recover()[0].decision.action, "query_remote")
        completed = self.coordinator.succeed("page-1", "artifact-1", ProviderUsage(total_tokens=0), "unknown")
        self.assertEqual(completed.state, "succeeded")
        self.assertEqual(self.coordinator.recover()[0].decision.action, "already_complete")

    def test_failure_retry_requires_idempotency_and_advances_attempt(self):
        self.coordinator.plan([self.units[0]])
        no_idempotency = ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg")
        self.coordinator.submit("page-1", no_idempotency)
        self.coordinator.fail("page-1", "rate_limit", retryable=True)
        with self.assertRaises(ParseError):
            self.coordinator.submit("page-1", no_idempotency)
        retryable = no_idempotency.model_copy(update={"idempotency_supported": True})
        self.store.save_invocation(self.coordinator.current("page-1").model_copy(update={"provider_job": retryable}))
        retried = self.coordinator.submit("page-1", retryable)
        self.assertEqual(retried.attempt, 2)

    def test_cancel_and_terminal_conflicts(self):
        self.coordinator.plan(self.units)
        self.assertEqual(self.coordinator.cancel("page-1").state, "cancelled")
        self.assertEqual(self.coordinator.cancel("page-1").state, "cancelled")
        with self.assertRaises(ParseError):
            self.coordinator.submit("page-1")
        self.coordinator.submit("page-2")
        self.coordinator.succeed("page-2", "artifact-2")
        with self.assertRaises(ParseError):
            self.coordinator.cancel("page-2")

    def test_failed_without_safe_retry_is_manual(self):
        self.coordinator.plan([self.units[0]])
        self.coordinator.submit("page-1")
        self.coordinator.unknown("page-1", "timeout")
        decision = self.coordinator.recover()[0].decision
        self.assertEqual(decision.action, "manual_review")


if __name__ == "__main__":
    unittest.main()
