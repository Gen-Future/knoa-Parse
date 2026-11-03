"""Internal lifecycle coordinator for persisted provider invocations."""
from typing import Literal

from pydantic import Field

from knoa_parse.core.errors import ParseError
from knoa_parse.core.provider_runs import (
    InvocationRecord, ProviderJobRef, ProviderUsage, RecoveryDecision, decide_recovery,
)
from knoa_parse.core.store import Store
from knoa_parse.core.models import Model


class InvocationUnit(Model):
    unit_id: str = Field(min_length=1, max_length=200)
    request_fingerprint: str = Field(pattern="^[a-f0-9]{64}$")


class InvocationDecision(Model):
    unit_id: str
    decision: RecoveryDecision


class InvocationCoordinator:
    """Coordinates durable state only; it never calls a Provider."""

    def __init__(self, store: Store, run_id: str, provider: str, operation: str,
                 config_fingerprint: str, *, max_attempts: int = 2):
        if not run_id or not provider or not operation:
            raise ValueError("Invocation coordinator identity is required")
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.store = store
        self.run_id = run_id
        self.provider = provider
        self.operation = operation
        self.config_fingerprint = config_fingerprint
        self.max_attempts = max_attempts

    def _id(self, unit_id: str) -> str:
        return f"{self.run_id}:{unit_id}"

    def plan(self, units: list[InvocationUnit]) -> list[InvocationRecord]:
        if not units or len({unit.unit_id for unit in units}) != len(units):
            raise ParseError("invocation_conflict", "Invocation units must be unique", 409)
        records = [InvocationRecord(
            id=self._id(unit.unit_id), run_id=self.run_id, unit_id=unit.unit_id,
            provider=self.provider, operation=self.operation,
            config_fingerprint=self.config_fingerprint,
            request_fingerprint=unit.request_fingerprint,
        ) for unit in units]
        return self.store.insert_invocations(records)

    def current(self, unit_id: str) -> InvocationRecord:
        return self.store.invocation(self._id(unit_id))

    def submit(self, unit_id: str, provider_job: ProviderJobRef | None = None) -> InvocationRecord:
        current = self.current(unit_id)
        if current.state == "submitted":
            if provider_job and current.provider_job and provider_job != current.provider_job:
                raise ParseError("invocation_conflict", "Submitted invocation has a different remote job", 409)
            return current
        if current.state == "planned":
            next_attempt = 1
        elif current.state == "failed":
            decision = decide_recovery(current, max_attempts=self.max_attempts)
            if decision.action != "retry":
                raise ParseError("invocation_conflict", decision.reason, 409)
            next_attempt = current.attempt + 1
        else:
            raise ParseError("invocation_conflict", "Invocation is not ready for submission", 409)
        updated = current.model_copy(update={
            "state": "submitted", "attempt": next_attempt, "billing_state": "pending",
            "provider_job": provider_job or current.provider_job, "error_code": None,
            "response_artifact_id": None,
        })
        return self.store.save_invocation(updated, expected_state=current.state)

    def succeed(self, unit_id: str, response_artifact_id: str, usage: ProviderUsage | None = None,
                billing_state: Literal["known", "unknown"] = "known") -> InvocationRecord:
        current = self.current(unit_id)
        if current.state == "succeeded" and current.response_artifact_id == response_artifact_id:
            return current
        if current.state not in {"submitted", "unknown"}:
            raise ParseError("invocation_conflict", "Invocation is not awaiting a result", 409)
        updated = current.model_copy(update={"state": "succeeded", "billing_state": billing_state,
                                             "error_code": None, "response_artifact_id": response_artifact_id,
                                             "usage": usage})
        return self.store.save_invocation(updated, expected_state=current.state)

    def fail(self, unit_id: str, error_code: str, *, retryable: bool,
             billing_state: Literal["known", "unknown"] = "known") -> InvocationRecord:
        current = self.current(unit_id)
        if current.state not in {"submitted", "unknown"}:
            raise ParseError("invocation_conflict", "Invocation is not awaiting a result", 409)
        updated = current.model_copy(update={"state": "failed", "error_code": error_code,
                                             "retryable": retryable, "billing_state": billing_state,
                                             "response_artifact_id": None})
        return self.store.save_invocation(updated, expected_state=current.state)

    def unknown(self, unit_id: str, error_code: str, provider_job: ProviderJobRef | None = None) -> InvocationRecord:
        current = self.current(unit_id)
        if current.state not in {"submitted", "unknown"}:
            raise ParseError("invocation_conflict", "Invocation is not awaiting a result", 409)
        updated = current.model_copy(update={"state": "unknown", "error_code": error_code,
                                             "billing_state": "unknown", "provider_job": provider_job or current.provider_job,
                                             "response_artifact_id": None})
        return self.store.save_invocation(updated, expected_state=current.state)

    def cancel(self, unit_id: str) -> InvocationRecord:
        current = self.current(unit_id)
        if current.state == "cancelled":
            return current
        if current.state not in {"planned", "submitted", "unknown"}:
            raise ParseError("invocation_conflict", "Invocation cannot be cancelled", 409)
        updated = current.model_copy(update={"state": "cancelled", "billing_state": current.billing_state,
                                             "error_code": None, "response_artifact_id": None})
        return self.store.save_invocation(updated, expected_state=current.state)

    def recover(self) -> list[InvocationDecision]:
        return [InvocationDecision(unit_id=record.unit_id,
                                   decision=decide_recovery(record, max_attempts=self.max_attempts))
                for record in self.store.list_invocations(self.run_id)]
