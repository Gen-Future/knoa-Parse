"""Media coverage and cost summaries kept separate from ParseResult."""
from typing import Literal

from pydantic import Field, model_validator

from .models import Model


class MediaChunkOutcome(Model):
    chunk_id: str = Field(min_length=1, max_length=200)
    core_start_ms: int = Field(ge=0)
    core_end_ms: int = Field(gt=0)
    status: Literal["completed", "failed"]
    issue_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def range_and_issue(self):
        if self.core_end_ms <= self.core_start_ms:
            raise ValueError("Chunk outcome range must be forward")
        if self.status == "failed" and not self.issue_code:
            raise ValueError("Failed chunk requires an issue code")
        if self.status == "completed" and self.issue_code:
            raise ValueError("Completed chunk cannot hide an issue")
        return self


class MediaCoverage(Model):
    requested_start_ms: int = Field(ge=0)
    requested_end_ms: int = Field(gt=0)
    covered_ms: int = Field(ge=0)
    missing_ranges: list[list[int]] = Field(default_factory=list, max_length=10000)
    status: Literal["completed", "partial", "failed"]

    @model_validator(mode="after")
    def valid_coverage(self):
        if self.requested_end_ms <= self.requested_start_ms:
            raise ValueError("Requested media range must be forward")
        requested = self.requested_end_ms - self.requested_start_ms
        if self.covered_ms > requested:
            raise ValueError("Covered media exceeds requested range")
        if self.status == "completed" and (self.missing_ranges or self.covered_ms != requested):
            raise ValueError("Completed media coverage cannot contain gaps")
        if self.status == "failed" and self.covered_ms != 0:
            raise ValueError("Failed media coverage cannot retain covered time")
        for start, end in self.missing_ranges:
            if start < self.requested_start_ms or end > self.requested_end_ms or end <= start:
                raise ValueError("Invalid missing media range")
        return self


class MediaCostSummary(Model):
    billing_state: Literal["not_sent", "known", "unknown"]
    cost_micros: int | None = Field(default=None, ge=0)
    observed_chunks: int = Field(ge=0)

    @model_validator(mode="after")
    def unknown_cost_not_zero(self):
        if self.billing_state == "unknown" and self.cost_micros is not None:
            raise ValueError("Unknown media cost cannot be represented as a number")
        if self.billing_state == "not_sent" and self.cost_micros is not None:
            raise ValueError("Unsent media work cannot have a cost")
        if self.billing_state == "known" and self.cost_micros is None:
            raise ValueError("Known media cost must be explicit")
        return self


class MediaExecutionSummary(Model):
    target: Literal["transcribe", "video_understanding"]
    coverage: MediaCoverage
    cost: MediaCostSummary

