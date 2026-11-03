"""Provider invocation ledger and conservative recovery decisions.

This is a persistence-neutral contract. It deliberately does not call a provider,
write SQLite, or infer whether an unknown remote request was billed.
"""
from typing import Literal

from pydantic import Field, model_validator

from .models import Model


InvocationState = Literal["planned", "submitted", "succeeded", "failed", "unknown", "cancelled"]
BillingState = Literal["not_sent", "pending", "known", "unknown"]


class ProviderJobRef(Model):
    provider: str = Field(min_length=1, max_length=100)
    remote_job_id: str = Field(min_length=1, max_length=500)
    config_version: str = Field(min_length=1, max_length=200)
    query_supported: bool = False
    cancel_supported: bool = False
    idempotency_supported: bool = False


class ProviderUsage(Model):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_micros: int | None = Field(default=None, ge=0)


class InvocationRecord(Model):
    id: str = Field(min_length=1, max_length=200)
    run_id: str = Field(min_length=1, max_length=200)
    unit_id: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    operation: str = Field(min_length=1, max_length=100)
    config_fingerprint: str = Field(pattern="^[a-f0-9]{64}$")
    request_fingerprint: str = Field(pattern="^[a-f0-9]{64}$")
    state: InvocationState = "planned"
    attempt: int = Field(default=0, ge=0)
    retryable: bool = False
    billing_state: BillingState = "not_sent"
    provider_job: ProviderJobRef | None = None
    usage: ProviderUsage | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=100)
    response_artifact_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def consistent(self):
        if self.state == "planned":
            if self.attempt or self.billing_state != "not_sent" or self.error_code or self.response_artifact_id:
                raise ValueError("Planned invocation cannot contain an attempt or outcome")
        elif self.state == "submitted":
            if self.attempt < 1 or self.billing_state not in {"pending", "unknown"}:
                raise ValueError("Submitted invocation must have a pending or unknown billing state")
            if self.error_code or self.response_artifact_id:
                raise ValueError("Submitted invocation cannot contain a terminal result")
        elif self.state == "succeeded":
            if self.attempt < 1 or self.error_code or not self.response_artifact_id:
                raise ValueError("Succeeded invocation requires an attempt and response artifact")
        elif self.state == "failed":
            if self.attempt < 1 or not self.error_code or self.response_artifact_id:
                raise ValueError("Failed invocation requires an attempt and error code")
        elif self.state == "unknown":
            if self.attempt < 1 or not self.error_code or self.billing_state not in {"pending", "unknown"}:
                raise ValueError("Unknown invocation requires an attempt, error and unresolved billing")
        elif self.state == "cancelled":
            if self.attempt == 0 and self.billing_state != "not_sent":
                raise ValueError("Unsent cancellation must remain not_sent")
            if self.attempt > 0 and self.billing_state == "not_sent":
                raise ValueError("Sent cancellation cannot be marked not_sent")
        if self.response_artifact_id and self.state != "succeeded":
            raise ValueError("Only succeeded invocations may reference a response artifact")
        return self


class RecoveryDecision(Model):
    action: Literal["submit", "retry", "query_remote", "already_complete", "skip", "manual_review"]
    reason: str = Field(min_length=1, max_length=500)
    safe_to_retry: bool = False


def decide_recovery(record: InvocationRecord, *, max_attempts: int = 2) -> RecoveryDecision:
    """Return a conservative next action without mutating the invocation."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if record.state == "planned":
        return RecoveryDecision(action="submit", reason="Invocation has not been sent")
    if record.state == "succeeded":
        return RecoveryDecision(action="already_complete", reason="Invocation has a retained response")
    if record.state == "cancelled":
        if record.billing_state == "not_sent":
            return RecoveryDecision(action="skip", reason="Cancellation happened before sending")
        return RecoveryDecision(action="manual_review", reason="Cancellation followed a sent request with unresolved billing")
    if record.state in {"submitted", "unknown"}:
        if record.provider_job and record.provider_job.query_supported:
            return RecoveryDecision(action="query_remote", reason="Remote state can be queried")
        return RecoveryDecision(action="manual_review", reason="Remote request may have been billed and cannot be queried safely")
    # failed
    if record.billing_state in {"pending", "unknown"}:
        if record.provider_job and record.provider_job.query_supported:
            return RecoveryDecision(action="query_remote", reason="Failed request has unresolved remote state")
        return RecoveryDecision(action="manual_review", reason="Failed request has unresolved billing")
    if not record.retryable:
        return RecoveryDecision(action="manual_review", reason="Provider marked failure as non-retryable")
    if record.attempt >= max_attempts:
        return RecoveryDecision(action="manual_review", reason="Maximum attempts reached")
    if record.provider_job and not record.provider_job.idempotency_supported:
        return RecoveryDecision(action="manual_review", reason="Retry could duplicate a remote request")
    return RecoveryDecision(action="retry", reason="Retryable failure was not sent or is known unbilled", safe_to_retry=True)


class InvocationLedger(Model):
    records: list[InvocationRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_units(self):
        keys = [(record.run_id, record.unit_id) for record in self.records]
        if len(keys) != len(set(keys)):
            raise ValueError("A run cannot contain duplicate invocation units")
        return self

    def snapshot(self) -> list[InvocationRecord]:
        return sorted(self.records, key=lambda record: (record.run_id, record.unit_id, record.id))
