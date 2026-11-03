"""Authored offline responses only. This is NOT an OCR engine or service adapter."""
import hashlib

from knoa_parse.core.document_analysis import DocumentCapability, PageAnalysis, PreparedPage, RecognizedElement
from knoa_parse.core.models import Artifact, Block, Coverage, Issue, PageRegion, ParseResult, Source
from knoa_parse.core.text_model import ProviderError


def fixture():
    original = b"synthetic source identity, not an actual PDF"
    digest = hashlib.sha256(original).hexdigest()
    source = Source(id="source-synthetic", revision=digest, filename="synthetic.pdf", media_type="application/pdf",
                    sha256=digest, size_bytes=len(original))
    original_artifact = Artifact(id=source.id, role="source", media_type=source.media_type, sha256=digest, size_bytes=len(original))
    native = ParseResult(schema_version="0.2.0-draft.1", source=source, status="partial", engine="synthetic-native",
                         artifacts=[original_artifact], blocks=[Block(
                             id="heading", kind="text", text="已有中文页眉",
                             locators=[PageRegion(artifact_id=source.id, precision="source_exact", page=1,
                                                  bbox=[0.0, 0.0, 100.0, 20.0], unit="pt", origin="top_left")])],
                         coverage=[Coverage(unit_id=f"page-{p}", status="failed", issue_codes=["external_ocr_required"]) for p in (1, 2)],
                         issues=[Issue(code="external_ocr_required", severity="error", message="Synthetic unread body")])
    pages = []
    for number in (1, 2):
        content = f"synthetic page {number}, not raster bytes".encode()
        pages.append(PreparedPage(source_id=source.id, source_sha256=digest, source_artifact_id=source.id, page=number,
                                  artifact=Artifact(id=f"page-image-{number}", role="derived", media_type="image/png",
                                                    sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)),
                                  width_px=1200, height_px=1600, width_pt=600.0, height_pt=800.0, content=content))
    return native, pages


class ScriptedDocumentProvider:
    """Explicit mock: prewritten text/coordinates; no image decoding, inference or I/O."""
    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {
            1: PageAnalysis(page=1, model="mock-authored", elements=[RecognizedElement(
                text="人工预写的正文，不是识别结果", bbox=[0.1, 0.2, 0.5, 0.4], unit="normalized", origin="top_left")]),
            2: ProviderError("provider_timeout", "Synthetic timeout", retryable=True),
        }

    def describe(self):
        return DocumentCapability(provider="scripted-mock", version="1", execution="mock", media_types=["image/png"],
                                  max_page_bytes=1024 * 1024, max_pixels=4_000_000, coordinate_units=["px", "normalized"])

    def analyze_page(self, request):
        self.calls.append(request)
        result = self.responses[request.page.page]
        if isinstance(result, Exception):
            raise result
        return result
