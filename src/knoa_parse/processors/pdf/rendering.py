"""Controlled PDF renderer seam; concrete rendering engines remain opt-in."""
from dataclasses import dataclass
from typing import Protocol

from pydantic import Field

from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Model, ParseResult, Source
from .page_inputs import PdfPageSpec, RasterPageInput, prepare_pages


class RenderBudget(Model):
    max_pages: int = Field(default=20, gt=0, le=100)
    max_page_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=64 * 1024 * 1024)
    max_total_bytes: int = Field(default=40 * 1024 * 1024, gt=0, le=128 * 1024 * 1024)
    max_pixels: int = Field(default=40_000_000, gt=0, le=200_000_000)


@dataclass(frozen=True)
class PdfRenderRequest:
    source: Source
    content: bytes
    pages: tuple[PdfPageSpec, ...]
    budget: RenderBudget


class PdfRenderer(Protocol):
    def render(self, request: PdfRenderRequest) -> list[RasterPageInput]: ...


def render_and_prepare(
    native: ParseResult,
    content: bytes,
    specs: list[PdfPageSpec],
    renderer: PdfRenderer,
    budget: RenderBudget | None = None,
):
    """Run a supplied renderer once, then atomically pass output through M3-C."""
    import hashlib

    budget = budget or RenderBudget()
    native = ParseResult.model_validate(native.model_dump())
    source = native.source
    if source.media_type != "application/pdf":
        raise ParseError("invalid_page_input", "Rendering requires a PDF source")
    if not isinstance(content, bytes) or len(content) != source.size_bytes or hashlib.sha256(content).hexdigest() != source.sha256:
        raise ParseError("source_corrupt", "PDF bytes do not match the fixed source")
    if not specs or len(specs) > budget.max_pages:
        raise ParseError("resource_limit", "Requested pages exceed the rendering page budget")
    if len({spec.page for spec in specs}) != len(specs):
        raise ParseError("invalid_page_input", "Requested pages contain duplicates")
    known = {coverage.unit_id for coverage in native.coverage}
    if any(f"page-{spec.page}" not in known for spec in specs):
        raise ParseError("invalid_page_input", "Requested page is not present in the native result")
    request = PdfRenderRequest(source=source, content=content, pages=tuple(sorted(specs, key=lambda item: item.page)), budget=budget)
    try:
        rasters = renderer.render(request)
    except ParseError:
        raise
    except Exception:
        raise ParseError("render_failed", "PDF renderer failed") from None
    if not isinstance(rasters, list):
        raise ParseError("render_failed", "PDF renderer returned an invalid page collection")
    total_bytes = 0
    for raster in rasters:
        if len(raster.content) > budget.max_page_bytes or raster.width_px * raster.height_px > budget.max_pixels:
            raise ParseError("resource_limit", "Rendered page exceeds the rendering budget")
        total_bytes += len(raster.content)
    if total_bytes > budget.max_total_bytes:
        raise ParseError("resource_limit", "Rendered pages exceed the total rendering budget")
    return prepare_pages(native, specs, rasters)
