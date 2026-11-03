"""Single-page external Provider execution boundary.

This module is opt-in and not registered by the native extraction worker. It
connects the durable invocation lifecycle to one injected Provider while keeping
unknown remote outcomes conservative.
"""
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import Field

from knoa_parse.core.document_analysis import DocumentAnalysisProvider, PageAnalysis, PageRequest
from knoa_parse.core.errors import ParseError, ProviderError
from knoa_parse.core.provider_runs import InvocationRecord, ProviderUsage
from knoa_parse.enrichment.invocations import InvocationCoordinator
from knoa_parse.core.models import Model


class ResponseArtifactPublisher(Protocol):
    def __call__(self, response: PageAnalysis, invocation_id: str) -> str: ...


class ProviderExecutionOutcome(Model):
    unit_id: str
    status: Literal["succeeded", "unknown", "cancelled", "already_complete", "manual_review"]
    invocation: InvocationRecord
    response: PageAnalysis | None = None
    error_code: str | None = Field(default=None, min_length=1)


def execute_page(
    coordinator: InvocationCoordinator,
    unit_id: str,
    request: PageRequest,
    provider: DocumentAnalysisProvider,
    publish_response: ResponseArtifactPublisher,
    *,
    cancelled: Callable[[], bool] = lambda: False,
) -> ProviderExecutionOutcome:
    """Execute one page exactly once and persist every externally visible outcome."""
    current = coordinator.current(unit_id)
    if current.state == "succeeded":
        return ProviderExecutionOutcome(unit_id=unit_id, status="already_complete", invocation=current)
    if current.state == "cancelled":
        return ProviderExecutionOutcome(unit_id=unit_id, status="cancelled", invocation=current)
    if current.state == "unknown":
        return ProviderExecutionOutcome(unit_id=unit_id, status="manual_review", invocation=current,
                                       error_code=current.error_code)
    if cancelled():
        record = coordinator.cancel(unit_id)
        return ProviderExecutionOutcome(unit_id=unit_id, status="cancelled", invocation=record)

    submitted = coordinator.submit(unit_id)
    try:
        response = PageAnalysis.model_validate(provider.analyze_page(request.model_copy(deep=True)).model_dump())
        if cancelled():
            record = coordinator.unknown(unit_id, "cancelled_after_send")
            return ProviderExecutionOutcome(unit_id=unit_id, status="unknown", invocation=record,
                                           error_code="cancelled_after_send")
        artifact_id = publish_response(response, submitted.id)
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("Response publisher returned an invalid artifact ID")
        record = coordinator.succeed(unit_id, artifact_id,
                                     ProviderUsage(total_tokens=response.total_tokens), billing_state="unknown")
        return ProviderExecutionOutcome(unit_id=unit_id, status="succeeded", invocation=record, response=response)
    except ProviderError as error:
        record = coordinator.unknown(unit_id, error.code)
        return ProviderExecutionOutcome(unit_id=unit_id, status="unknown", invocation=record, error_code=error.code)
    except ParseError as error:
        record = coordinator.unknown(unit_id, error.code)
        return ProviderExecutionOutcome(unit_id=unit_id, status="unknown", invocation=record, error_code=error.code)
    except Exception:
        record = coordinator.unknown(unit_id, "provider_execution_unknown")
        return ProviderExecutionOutcome(unit_id=unit_id, status="unknown", invocation=record,
                                       error_code="provider_execution_unknown")


def execute_pages(
    coordinator: InvocationCoordinator,
    requests: list[tuple[str, PageRequest]],
    provider: DocumentAnalysisProvider,
    publish_response: ResponseArtifactPublisher,
    *,
    cancelled: Callable[[], bool] = lambda: False,
) -> list[ProviderExecutionOutcome]:
    """Execute planned pages in order; never retries or silently skips a page."""
    outcomes = []
    for unit_id, request in requests:
        outcome = execute_page(coordinator, unit_id, request, provider, publish_response, cancelled=cancelled)
        outcomes.append(outcome)
        if cancelled():
            for remaining, _ in requests[len(outcomes):]:
                current = coordinator.current(remaining)
                if current.state == "planned":
                    outcomes.append(ProviderExecutionOutcome(unit_id=remaining, status="cancelled",
                                                             invocation=coordinator.cancel(remaining)))
            break
    return outcomes
