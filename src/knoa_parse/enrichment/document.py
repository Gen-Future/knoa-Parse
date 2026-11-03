"""Explicit, bounded page orchestration; never invoked by the native worker."""
import hashlib
import time
import uuid
from collections.abc import Callable
from typing import Literal

from pydantic import Field

from knoa_parse.core.document_analysis import (
    AnalysisContext, DocumentAnalysisProvider, DocumentCapability, PageAnalysis, PageRequest, PreparedPage,
)
from knoa_parse.core.errors import ParseError, ProviderError
from knoa_parse.core.models import Block, Model, PageRegion, ParseResult


class AnalysisBudget(Model):
    max_pages: int = Field(default=20, gt=0, le=100)
    max_input_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_calls: int = Field(default=20, gt=0, le=100)
    max_seconds: float = Field(default=60.0, gt=0, le=300)
    max_blocks: int = Field(default=2000, gt=0)
    max_text_chars: int = Field(default=200000, gt=0)
    max_context_chars: int = Field(default=4000, ge=0)
    max_context_blocks: int = Field(default=20, ge=0)


class PageOutcome(Model):
    page: int
    status: Literal["completed", "failed", "not_sent"]
    code: str | None = None


class Invocation(Model):
    page: int
    trace_id: str
    provider: str
    provider_version: str
    execution: Literal["external_service", "mock"]
    input_artifact_id: str
    input_sha256: str
    context: list[AnalysisContext]
    status: Literal["unknown", "discarded", "completed"]
    code: str | None = None
    retryable: bool = False
    model: str | None = None
    total_tokens: int | None = None
    # Unknown is not free. This foundation does not estimate fees or enforce money caps.
    cost: None = None


class AnalysisReport(Model):
    kind: Literal["document_analysis_experiment"] = "document_analysis_experiment"
    dry_run: bool
    source_id: str
    source_sha256: str
    status: Literal["completed", "partial", "failed"]
    pages: list[PreparedPage]
    outcomes: list[PageOutcome]
    blocks: list[Block]
    invocations: list[Invocation]
    total_tokens: int | None


def select_context(native: ParseResult, page: int, budget: AnalysisBudget) -> list[AnalysisContext]:
    """Only unambiguous same-source/same-page native text, in retained input order."""
    source_id = next(a.id for a in native.artifacts if a.role == "source")
    remaining = budget.max_context_chars
    selected = []
    for block in native.blocks:
        if remaining <= 0 or len(selected) >= budget.max_context_blocks:
            break
        locations = block.locators
        if not block.text or block.acquisition != "native" or not all(
            isinstance(loc, PageRegion) and loc.artifact_id == source_id and loc.page == page
            for loc in locations
        ):
            continue
        text = block.text[:remaining]
        selected.append(AnalysisContext(block_id=block.id, text=text, truncated=len(text) < len(block.text)))
        remaining -= len(text)
    return selected


def analyze_pages(
    native: ParseResult,
    pages: list[PreparedPage],
    provider: DocumentAnalysisProvider | None,
    budget: AnalysisBudget | None = None,
    *,
    dry_run: bool = False,
    cancelled: Callable[[], bool] = lambda: False,
    clock: Callable[[], float] = time.monotonic,
) -> AnalysisReport:
    """Return a separate experiment report, never promote mock to ParseResult.

    Caller supplies validated full-page rasters and dimensions; raster preparation and
    original-page geometry verification are prerequisites, not implemented here.
    Deadline checks bracket synchronous calls; providers must honor the timeout hint.
    """
    budget = budget or AnalysisBudget()
    native = ParseResult.model_validate(native.model_dump())
    pages = [PreparedPage.model_validate(p.model_dump(exclude={"content"}) | {"content": p.content}) for p in pages]
    if provider is None:
        raise ParseError("missing_capability", "No document analysis provider configured")
    capability = provider.describe()
    # Revalidate rather than trust constructed/mutated objects from a plugin.
    capability = DocumentCapability.model_validate(capability.model_dump())
    if capability.execution == "mock" and not dry_run:
        raise ParseError("mock_not_allowed", "Mock analysis requires explicit dry_run")
    if not pages or len(pages) > budget.max_pages or sum(p.artifact.size_bytes for p in pages) > budget.max_input_bytes:
        raise ParseError("resource_limit", "Page selection exceeds the input budget")
    source = next(a for a in native.artifacts if a.role == "source")
    if native.source.media_type != "application/pdf":
        raise ParseError("invalid_page_input", "This foundation only accepts prepared PDF pages")
    known_pages = {c.unit_id for c in native.coverage}
    seen_pages, seen_artifacts = set(), {a.id for a in native.artifacts}
    for page in pages:
        if (page.source_id, page.source_sha256, page.source_artifact_id) != (native.source.id, native.source.sha256, source.id):
            raise ParseError("invalid_page_input", "Page does not belong to the source")
        if f"page-{page.page}" not in known_pages or page.page in seen_pages:
            raise ParseError("invalid_page_input", "Unknown or duplicate source page")
        artifact = page.artifact
        if artifact.role != "derived" or artifact.id in seen_artifacts or artifact.media_type not in capability.media_types:
            raise ParseError("invalid_page_input", "Unsupported or ambiguous page artifact")
        if artifact.size_bytes != len(page.content) or artifact.sha256 != hashlib.sha256(page.content).hexdigest():
            raise ParseError("invalid_page_input", "Page bytes do not match artifact")
        if len(page.content) > capability.max_page_bytes or page.width_px * page.height_px > capability.max_pixels:
            raise ParseError("resource_limit", "Page exceeds provider limits")
        seen_pages.add(page.page)
        seen_artifacts.add(artifact.id)
    pages.sort(key=lambda p: p.page)
    invocations, blocks, outcomes = [], [], []
    deadline = clock() + budget.max_seconds
    total_chars = 0
    run_id = uuid.uuid4().hex
    for page in pages:
        remaining = deadline - clock()
        code = "cancelled" if cancelled() else "deadline_exceeded" if remaining <= 0 else (
            "call_budget_exceeded" if len(invocations) >= budget.max_calls else None
        )
        if code:
            outcomes.append(PageOutcome(page=page.page, status="not_sent", code=code))
            continue
        context = select_context(native, page.page, budget)
        request = PageRequest(page=page, context=context, timeout_seconds=remaining, trace_id=f"{run_id}:{page.page}")
        invocation = Invocation(
            page=page.page, trace_id=request.trace_id, provider=capability.provider,
            provider_version=capability.version, execution=capability.execution,
            input_artifact_id=page.artifact.id, input_sha256=page.artifact.sha256,
            context=context, status="unknown",
        )
        invocations.append(invocation)
        try:
            response = provider.analyze_page(request.model_copy(deep=True))
            response = PageAnalysis.model_validate(response.model_dump())
            invocation.model, invocation.total_tokens = response.model, response.total_tokens
            if cancelled():
                raise ParseError("cancelled", "Cancelled after sending")
            if clock() >= deadline:
                raise ParseError("deadline_exceeded", "Deadline exceeded after sending")
            if response.page != page.page:
                raise ParseError("invalid_provider_response", "Provider returned the wrong page")
            if len(blocks) + len(response.elements) > budget.max_blocks or total_chars + sum(len(e.text) for e in response.elements) > budget.max_text_chars:
                raise ParseError("output_budget_exceeded", "Response exceeds the output budget")
            pending = []
            for index, element in enumerate(response.elements):
                if element.unit not in capability.coordinate_units:
                    raise ParseError("invalid_provider_response", "Undeclared coordinate unit")
                width, height = (1.0, 1.0) if element.unit == "normalized" else (page.width_px, page.height_px)
                left, top, right, bottom = element.bbox
                if right > width or max(top, bottom) > height:
                    raise ParseError("invalid_provider_response", "Region outside input page")
                if element.origin == "bottom_left":
                    top, bottom = height - top, height - bottom
                bbox = [left / width * page.width_pt, top / height * page.height_pt,
                        right / width * page.width_pt, bottom / height * page.height_pt]
                block_id = f"analysis:{run_id}:{page.page}:{index}"
                if block_id in {b.id for b in native.blocks}:
                    raise ParseError("invalid_provider_response", "Block identity collision")
                pending.append(Block(
                    id=block_id, kind=element.kind, text=element.text,
                    acquisition="ocr" if element.kind == "text" else "inferred",
                    context_block_ids=[item.block_id for item in context],
                    # Inferred source areas are not exact OCR evidence. Provider OCR
                    # coordinates are also estimated until real adapter calibration.
                    locators=[PageRegion(artifact_id=source.id, precision="estimated", page=page.page,
                                         bbox=bbox, unit="pt", origin="top_left")],
                ))
            blocks.extend(pending)
            total_chars += sum(len(b.text or "") for b in pending)
            invocation.status = "completed"
            outcomes.append(PageOutcome(page=page.page, status="completed"))
        except Exception as error:
            # No raw provider messages, bodies or credentials enter the report.
            allowed = {"cancelled", "deadline_exceeded", "output_budget_exceeded", "invalid_provider_response",
                       "provider_timeout", "provider_unavailable", "provider_rate_limited", "provider_auth_failed",
                       "provider_resource_limit", "provider_invalid_response", "provider_response_limit",
                       "provider_redirect", "provider_billing_required", "provider_not_found",
                       "provider_invalid_request", "provider_request_limit"}
            code = error.code if isinstance(error, ParseError) and error.code in allowed else "provider_error" if isinstance(error, ProviderError) else "invalid_provider_response"
            invocation.status = "unknown" if isinstance(error, ProviderError) or not isinstance(error, ParseError) else "discarded"
            invocation.code = code
            invocation.retryable = isinstance(error, ProviderError) and error.retryable
            outcomes.append(PageOutcome(page=page.page, status="failed", code=code))
    completed = sum(p.status == "completed" for p in outcomes)
    status = "completed" if completed == len(pages) else "partial" if completed else "failed"
    usage = None if any(i.total_tokens is None for i in invocations) else sum(i.total_tokens for i in invocations)
    return AnalysisReport(dry_run=dry_run, source_id=native.source.id, source_sha256=native.source.sha256,
                          status=status, pages=pages, outcomes=outcomes, blocks=blocks,
                          invocations=invocations, total_tokens=usage)
