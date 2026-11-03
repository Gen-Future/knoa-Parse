import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from m3_fixtures import ScriptedDocumentProvider, fixture

from knoa_parse.apps.worker.provider_execution import execute_page, execute_pages
from knoa_parse.core.document_analysis import PageRequest
from knoa_parse.core.errors import ProviderError
from knoa_parse.core.provider_runs import ProviderUsage
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store
from knoa_parse.enrichment.invocations import InvocationCoordinator, InvocationUnit


class ProviderExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Settings(Path(self.temp.name)))
        self.native, self.pages = fixture()
        self.provider = ScriptedDocumentProvider()
        self.coordinator = InvocationCoordinator(self.store, "run-1", "mock", "document_analysis", "a" * 64)
        self.units = [InvocationUnit(unit_id=f"page-{page.page}", request_fingerprint=(str(page.page) * 64))
                      for page in self.pages]
        self.coordinator.plan(self.units)
        self.requests = [(f"page-{page.page}", PageRequest(page=page, context=[], timeout_seconds=30,
                                                              trace_id=f"trace-{page.page}"))
                         for page in self.pages]
        self.published = []

    def tearDown(self):
        self.temp.cleanup()

    def publish(self, response, invocation_id):
        artifact_id = f"artifact-{invocation_id}"
        self.published.append((artifact_id, response.page))
        return artifact_id

    def test_success_publishes_before_marking_succeeded(self):
        self.provider.responses = {1: self.provider.responses[1]}
        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, self.publish)
        self.assertEqual(outcome.status, "succeeded")
        self.assertEqual(outcome.invocation.response_artifact_id, "artifact-run-1:page-1")
        self.assertEqual(outcome.invocation.usage, ProviderUsage(total_tokens=None))
        self.assertEqual(self.published, [("artifact-run-1:page-1", 1)])
        self.assertEqual(self.store.invocation("run-1:page-1").state, "succeeded")

    def test_provider_error_becomes_unknown_without_retry_or_publish(self):
        self.provider.responses[1] = ProviderError("provider_timeout", "synthetic", retryable=True)
        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, self.publish)
        self.assertEqual(outcome.status, "unknown")
        self.assertEqual(outcome.error_code, "provider_timeout")
        self.assertEqual(outcome.invocation.billing_state, "unknown")
        self.assertEqual(self.published, [])
        self.assertEqual(len(self.provider.calls), 1)

    def test_publisher_failure_becomes_unknown_and_does_not_claim_success(self):
        def broken(response, invocation_id):
            raise OSError("private response path")

        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, broken)
        self.assertEqual(outcome.status, "unknown")
        self.assertEqual(outcome.error_code, "provider_execution_unknown")
        self.assertEqual(self.store.invocation("run-1:page-1").state, "unknown")

    def test_cancel_before_send_does_not_call_provider(self):
        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, self.publish,
                               cancelled=lambda: True)
        self.assertEqual(outcome.status, "cancelled")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.store.invocation("run-1:page-1").billing_state, "not_sent")

    def test_cancel_after_send_is_unknown(self):
        calls = [0]

        def cancelled():
            calls[0] += 1
            return calls[0] >= 2

        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, self.publish,
                               cancelled=cancelled)
        self.assertEqual(outcome.status, "unknown")
        self.assertEqual(outcome.error_code, "cancelled_after_send")
        self.assertEqual(self.published, [])

    def test_multiple_pages_keep_partial_page_outcomes(self):
        self.provider.responses[2] = ProviderError("provider_unavailable", "synthetic", retryable=True)
        outcomes = execute_pages(self.coordinator, self.requests, self.provider, self.publish)
        self.assertEqual([item.status for item in outcomes], ["succeeded", "unknown"])
        self.assertEqual(self.store.invocation("run-1:page-1").state, "succeeded")
        self.assertEqual(self.store.invocation("run-1:page-2").state, "unknown")

    def test_completed_page_is_not_called_again(self):
        self.coordinator.submit("page-1")
        self.coordinator.succeed("page-1", "artifact-existing")
        outcome = execute_page(self.coordinator, "page-1", self.requests[0][1], self.provider, self.publish)
        self.assertEqual(outcome.status, "already_complete")
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.published, [])

    def test_cancelled_remaining_pages_are_recorded(self):
        calls = [0]

        def cancel_before_second():
            calls[0] += 1
            return calls[0] >= 3

        outcomes = execute_pages(self.coordinator, self.requests, self.provider, self.publish,
                                 cancelled=cancel_before_second)
        self.assertEqual([item.status for item in outcomes], ["succeeded", "cancelled"])
        self.assertEqual(self.provider.calls[0].page.page, 1)
        self.assertEqual(self.store.invocation("run-1:page-2").state, "cancelled")


if __name__ == "__main__":
    unittest.main()
