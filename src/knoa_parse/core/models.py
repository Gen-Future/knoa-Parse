"""Versioned, engine-independent evidence contract. Schema is generated from these models."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.2.0-draft.1"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Source(Model):
    id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    media_type: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class Artifact(Model):
    id: str = Field(min_length=1)
    role: Literal["source", "engine_result", "derived"]
    media_type: str
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class Location(Model):
    artifact_id: str
    precision: Literal["source_exact", "derived_exact", "estimated", "unavailable"]


class TextSpan(Location):
    kind: Literal["text_span"] = "text_span"
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    unit: Literal["unicode_code_point"] = "unicode_code_point"

    @model_validator(mode="after")
    def forward(self):
        if self.end <= self.start:
            raise ValueError("Text spans must be nonempty and forward")
        return self


class StructuredNode(Location):
    kind: Literal["structured_node"] = "structured_node"
    pointer: str


class DocumentNode(Location):
    kind: Literal["document_node"] = "document_node"
    pointer: str


class SheetRange(Location):
    kind: Literal["sheet_range"] = "sheet_range"
    sheet: str
    a1_range: str = Field(pattern="^[A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?$")


class PageRegion(Location):
    kind: Literal["page_region"] = "page_region"
    page: int = Field(ge=1)
    bbox: list[float] = Field(min_length=4, max_length=4)
    unit: Literal["pt", "px", "normalized"]
    origin: Literal["top_left", "bottom_left"]

    @model_validator(mode="after")
    def valid_box(self):
        left, top, right, bottom = self.bbox
        if right < left or (self.origin == "top_left" and bottom < top) or (self.origin == "bottom_left" and top < bottom):
            raise ValueError("Bounding box conflicts with the coordinate origin")
        if self.unit == "normalized" and any(v < 0 or v > 1 for v in self.bbox):
            raise ValueError("Normalized coordinates must be within [0,1]")
        return self


class MediaSegment(Location):
    kind: Literal["media_segment"] = "media_segment"
    stream_id: str
    start_ms: int = Field(ge=0)
    end_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def forward(self):
        if self.end_ms <= self.start_ms:
            raise ValueError("Media spans must be nonempty and forward")
        return self


Locator = Annotated[
    TextSpan | StructuredNode | DocumentNode | SheetRange | PageRegion | MediaSegment,
    Field(discriminator="kind"),
]


class Block(Model):
    id: str
    kind: Literal["text", "structured", "table", "image", "transcript", "description"]
    text: str | None = None
    data: dict | list | None = None
    acquisition: Literal["native", "ocr", "asr", "inferred"] = "native"
    locators: list[Locator] = Field(min_length=1)
    context_block_ids: list[str] = Field(default_factory=list)


class Issue(Model):
    code: str
    message: str
    severity: Literal["warning", "error"]
    unit_id: str | None = None


class Coverage(Model):
    unit_id: str
    status: Literal["completed", "skipped", "failed"]
    issue_codes: list[str] = Field(default_factory=list)


class ParseResult(Model):
    schema_version: Literal["0.2.0-draft.1"]
    source: Source
    target: Literal["native_extract"] = "native_extract"
    status: Literal["completed", "partial", "failed"]
    engine: str
    artifacts: list[Artifact] = Field(min_length=1)
    blocks: list[Block]
    coverage: list[Coverage] = Field(min_length=1)
    issues: list[Issue]

    @model_validator(mode="after")
    def consistent(self):
        artifact_ids = [a.id for a in self.artifacts]
        block_ids = [b.id for b in self.blocks]
        unit_ids = [c.unit_id for c in self.coverage]
        for label, ids in (("artifact", artifact_ids), ("block", block_ids), ("unit", unit_ids)):
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} IDs")
        sources = [a for a in self.artifacts if a.role == "source"]
        if len(sources) != 1 or (sources[0].sha256, sources[0].size_bytes) != (
            self.source.sha256, self.source.size_bytes
        ):
            raise ValueError("Source artifact must match source digest and size")
        for block in self.blocks:
            for locator in block.locators:
                if locator.artifact_id not in artifact_ids:
                    raise ValueError("Dangling artifact locator")
                artifact = next(a for a in self.artifacts if a.id == locator.artifact_id)
                if locator.precision == "source_exact" and artifact.role != "source":
                    raise ValueError("Source precision requires the original artifact")
            if not set(block.context_block_ids) <= set(block_ids) - {block.id}:
                raise ValueError("Invalid context references")
        codes = {i.code for i in self.issues}
        if any(i.unit_id is not None and i.unit_id not in unit_ids for i in self.issues):
            raise ValueError("Issue references unknown coverage unit")
        for unit in self.coverage:
            if not set(unit.issue_codes) <= codes:
                raise ValueError("Coverage references unknown issues")
            if unit.status == "failed" and not unit.issue_codes:
                raise ValueError("Failed coverage requires a reason")
        errors = any(i.severity == "error" for i in self.issues)
        gaps = any(c.status == "failed" for c in self.coverage)
        if self.status == "completed" and (errors or gaps):
            raise ValueError("Completed results cannot hide errors or missing units")
        if self.status == "failed" and (self.blocks or not errors):
            raise ValueError("Failed results require errors and cannot contain blocks")
        if self.status == "partial" and (not self.blocks or not (errors or gaps)):
            raise ValueError("Partial results require retained blocks and a gap")
        return self
