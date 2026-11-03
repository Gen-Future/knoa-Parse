import json
import unittest

from pydantic import ValidationError

from knoa_parse.core.provider_runs import (
    InvocationLedger, InvocationRecord, ProviderJobRef, ProviderUsage, decide_recovery,
)


def record(**changes):
    value = {
        "id": "inv-1", "run_id": "run-1", "unit_id": "page-1", "provider": "remote",
        "operation": "document_analysis", "config_fingerprint": "a" * 64,
        "request_fingerprint": "b" * 64,
    }
    value.update(changes)
    return InvocationRecord.model_validate(value)


class ProviderRunTests(unittest.TestCase):
    def test_planned_submission_success_and_failure_shapes(self):
        self.assertEqual(decide_recovery(record()).action, "submit")
        submitted = record(state="submitted", attempt=1, billing_state="pending")
        self.assertEqual(decide_recovery(submitted).action, "manual_review")
        success = record(state="succeeded", attempt=1, billing_state="known", response_artifact_id="artifact-1",
                         usage=ProviderUsage(total_tokens=0, cost_micros=0))
        self.assertEqual(decide_recovery(success).action, "already_complete")
        failed = record(state="failed", attempt=1, billing_state="known", retryable=False, error_code="bad_request")
        self.assertEqual(decide_recovery(failed).action, "manual_review")

    def test_unknown_remote_state_queries_only_when_supported(self):
        remote = ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg-1", query_supported=True)
        self.assertEqual(decide_recovery(record(state="unknown", attempt=1, billing_state="unknown", error_code="timeout",
                                                provider_job=remote)).action, "query_remote")
        remote = remote.model_copy(update={"query_supported": False})
        self.assertEqual(decide_recovery(record(state="unknown", attempt=1, billing_state="unknown", error_code="timeout",
                                                provider_job=remote)).action, "manual_review")

    def test_retry_requires_known_unbilled_or_unsent_and_idempotency(self):
        remote = ProviderJobRef(provider="remote", remote_job_id="job-1", config_version="cfg-1", idempotency_supported=True)
        retry = record(state="failed", attempt=1, billing_state="known", retryable=True, error_code="rate_limit",
                       provider_job=remote)
        self.assertEqual(decide_recovery(retry).action, "retry")
        self.assertTrue(decide_recovery(retry).safe_to_retry)
        unknown = retry.model_copy(update={"billing_state": "unknown"})
        self.assertEqual(decide_recovery(unknown).action, "manual_review")
        no_idempotency = retry.model_copy(update={"provider_job": remote.model_copy(update={"idempotency_supported": False})})
        self.assertEqual(decide_recovery(no_idempotency).action, "manual_review")
        self.assertEqual(decide_recovery(retry, max_attempts=1).action, "manual_review")

    def test_cancelled_is_skip_only_when_nothing_was_sent(self):
        self.assertEqual(decide_recovery(record(state="cancelled", billing_state="not_sent")).action, "skip")
        self.assertEqual(decide_recovery(record(state="cancelled", attempt=1, billing_state="unknown")).action, "manual_review")

    def test_state_invariants_reject_hidden_outcomes_and_jumps(self):
        for changes in (
            {"state": "planned", "attempt": 1},
            {"state": "submitted", "attempt": 0, "billing_state": "pending"},
            {"state": "succeeded", "attempt": 1, "billing_state": "known"},
            {"state": "failed", "attempt": 1, "billing_state": "known"},
            {"state": "unknown", "attempt": 1, "billing_state": "known", "error_code": "timeout"},
            {"state": "succeeded", "attempt": 1, "billing_state": "known", "response_artifact_id": "x", "error_code": "oops"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                record(**changes)

    def test_ledger_units_are_unique_and_snapshot_is_stable(self):
        second = record(id="inv-2", unit_id="page-2")
        ledger = InvocationLedger(records=[second, record()])
        self.assertEqual([item.unit_id for item in ledger.snapshot()], ["page-1", "page-2"])
        with self.assertRaises(ValidationError):
            InvocationLedger(records=[record(), record(id="inv-3")])

    def test_usage_zero_and_unknown_cost_are_distinct_and_json_is_safe(self):
        success = record(state="succeeded", attempt=1, billing_state="unknown", response_artifact_id="artifact-1",
                         usage=ProviderUsage(total_tokens=0, cost_micros=None))
        payload = json.loads(success.model_dump_json())
        self.assertEqual(payload["usage"]["total_tokens"], 0)
        self.assertIsNone(payload["usage"]["cost_micros"])
        self.assertNotIn("key", success.model_dump_json().lower())

    def test_fingerprints_are_fixed_length_hex(self):
        with self.assertRaises(ValidationError):
            record(request_fingerprint="private request body")
        with self.assertRaises(ValidationError):
            record(config_fingerprint="G" * 64)


if __name__ == "__main__":
    unittest.main()
