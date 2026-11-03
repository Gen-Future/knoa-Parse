"""Validate prepared full-page rasters before any external document request."""
import hashlib
import math
from typing import Literal

from pydantic import Field, model_validator

from knoa_parse.core.document_analysis import PreparedPage
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Artifact, ParseResult
from knoa_parse.core.models import Model


class PdfPageSpec(Model):
    page: int = Field(ge=1)
    width_pt: float = Field(gt=0)
    height_pt: float = Field(gt=0)
    rotation_degrees: Literal[0, 90, 180, 270] = 0
    crop: Literal["full_page"] = "full_page"

    @model_validator(mode="after")
    def finite_dimensions(self):
        if not all(math.isfinite(value) for value in (self.width_pt, self.height_pt)):
            raise ValueError("PDF page dimensions must be finite")
        return self


class RasterPageInput(Model):
    page: int = Field(ge=1)
    artifact_id: str = Field(min_length=1, max_length=200)
    media_type: Literal["image/png", "image/jpeg"]
    width_px: int = Field(gt=0)
    height_px: int = Field(gt=0)
    content: bytes = Field(min_length=1, exclude=True, repr=False)


def _upright_dimensions(spec: PdfPageSpec) -> tuple[float, float]:
    if spec.rotation_degrees in {90, 270}:
        return spec.height_pt, spec.width_pt
    return spec.width_pt, spec.height_pt


def prepare_pages(native: ParseResult, specs: list[PdfPageSpec], rasters: list[RasterPageInput]) -> list[PreparedPage]:
    """Atomically validate and bind full-page raster inputs to one native PDF."""
    native = ParseResult.model_validate(native.model_dump())
    if native.source.media_type != "application/pdf":
        raise ParseError("invalid_page_input", "Page preparation requires a PDF source")
    source_artifact = next((item for item in native.artifacts if item.role == "source"), None)
    if source_artifact is None:
        raise ParseError("invalid_page_input", "PDF result has no source artifact")
    if not specs or len(specs) != len(rasters):
        raise ParseError("invalid_page_input", "Page specifications and rasters must have the same nonzero pages")
    spec_by_page = {item.page: item for item in specs}
    raster_by_page = {item.page: item for item in rasters}
    if len(spec_by_page) != len(specs) or len(raster_by_page) != len(rasters) or set(spec_by_page) != set(raster_by_page):
        raise ParseError("invalid_page_input", "Page specifications and rasters contain duplicate or missing pages")
    known_pages = {coverage.unit_id for coverage in native.coverage}
    source_artifact_ids = {item.id for item in native.artifacts}
    if any(f"page-{page}" not in known_pages for page in spec_by_page):
        raise ParseError("invalid_page_input", "Raster page is not present in the native PDF result")
    output = []
    raster_ids = set()
    for page in sorted(spec_by_page):
        spec, raster = spec_by_page[page], raster_by_page[page]
        if spec.crop != "full_page":
            raise ParseError("invalid_page_input", "Only full-page rasters are accepted")
        if raster.artifact_id in source_artifact_ids or raster.artifact_id in raster_ids:
            raise ParseError("invalid_page_input", "Raster artifact ID collides with an existing artifact")
        digest = hashlib.sha256(raster.content).hexdigest()
        if not raster.content:
            raise ParseError("invalid_page_input", "Raster content is empty")
        upright_width, upright_height = _upright_dimensions(spec)
        expected_ratio = upright_width / upright_height
        actual_ratio = raster.width_px / raster.height_px
        if abs(actual_ratio - expected_ratio) > max(expected_ratio * 0.02, 1e-9):
            raise ParseError("invalid_page_input", "Raster aspect ratio does not match the full PDF page")
        artifact = Artifact(id=raster.artifact_id, role="derived", media_type=raster.media_type,
                            sha256=digest, size_bytes=len(raster.content))
        output.append(PreparedPage(
            source_id=native.source.id, source_sha256=native.source.sha256,
            source_artifact_id=source_artifact.id, page=page, artifact=artifact,
            width_px=raster.width_px, height_px=raster.height_px,
            width_pt=upright_width, height_pt=upright_height,
            source_width_pt=spec.width_pt, source_height_pt=spec.height_pt,
            rotation_degrees=spec.rotation_degrees, content=raster.content,
        ))
        raster_ids.add(raster.artifact_id)
    return output
