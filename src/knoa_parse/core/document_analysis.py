"""Internal synchronous page-analysis port. Not a public parsing capability."""
from typing import Literal, Protocol

from pydantic import Field, model_validator

from .models import Artifact, Model


class DocumentCapability(Model):
    provider: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    execution: Literal["external_service", "mock"]
    media_types: list[Literal["image/png", "image/jpeg"]] = Field(min_length=1)
    max_page_bytes: int = Field(gt=0)
    max_pixels: int = Field(gt=0)
    coordinate_units: list[Literal["px", "normalized"]] = Field(min_length=1)
    # This first port is synchronous, single-page, with no retry or remote cancel.


class PreparedPage(Model):
    source_id: str
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    source_artifact_id: str
    page: int = Field(ge=1)
    artifact: Artifact
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    width_pt: float = Field(gt=0)
    height_pt: float = Field(gt=0)
    source_width_pt: float | None = Field(default=None, gt=0)
    source_height_pt: float | None = Field(default=None, gt=0)
    rotation_degrees: Literal[0, 90, 180, 270] = 0
    mapping: Literal["full_page_upright"] = "full_page_upright"
    content: bytes = Field(min_length=1, exclude=True, repr=False)


class AnalysisContext(Model):
    block_id: str
    text: str
    truncated: bool


class PageRequest(Model):
    page: PreparedPage
    context: list[AnalysisContext]
    timeout_seconds: float = Field(gt=0)
    trace_id: str


class RecognizedElement(Model):
    kind: Literal["text", "description"] = "text"
    text: str = Field(min_length=1, max_length=100000)
    bbox: list[float] = Field(min_length=4, max_length=4)
    unit: Literal["px", "normalized"]
    origin: Literal["top_left", "bottom_left"]

    @model_validator(mode="after")
    def box(self):
        if not self.text.strip():
            raise ValueError("Recognized content cannot be whitespace only")
        left, top, right, bottom = self.bbox
        if right <= left or (self.origin == "top_left" and bottom <= top) or (
            self.origin == "bottom_left" and top <= bottom
        ):
            raise ValueError("Expected a nonempty region in the declared coordinate system")
        if min(self.bbox) < 0 or (self.unit == "normalized" and max(self.bbox) > 1):
            raise ValueError("Region out of bounds")
        return self


class PageAnalysis(Model):
    page: int = Field(ge=1)
    elements: list[RecognizedElement] = Field(max_length=10000)
    blank: bool = False
    model: str = Field(min_length=1, max_length=200)
    total_tokens: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def content_or_blank(self):
        if self.blank == bool(self.elements):
            raise ValueError("An empty page must be explicitly blank; blank pages cannot contain elements")
        return self


class DocumentAnalysisProvider(Protocol):
    def describe(self) -> DocumentCapability: ...

    def analyze_page(self, request: PageRequest) -> PageAnalysis: ...
