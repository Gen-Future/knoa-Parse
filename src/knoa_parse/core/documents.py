"""Engine-neutral document transfer objects and evidence assembly."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
import json

from .models import Artifact, Block, Coverage, DocumentNode, Issue, ParseResult, SCHEMA_VERSION, Source


class ArtifactSink(Protocol):
    def put(self, raw: bytes, role: str, media_type: str) -> Artifact: ...


@dataclass
class EngineItem:
    pointer: str
    kind: str
    text: str | None
    data: dict
    # Page positions are normalized by the engine. A page is not a sheet or slide.
    locations: list[dict] = field(default_factory=list)
    image: bytes | None = None
    image_media_type: str | None = None


@dataclass
class EngineDocument:
    payload: dict
    items: list[EngineItem]
    pages: list[int]
    issues: list[Issue]
    successful: bool


class NativeEngine(Protocol):
    def convert(self, source: Source, path: Path) -> EngineDocument: ...


class WorkbookInspector(Protocol):
    def inspect(self, path: Path) -> dict: ...


class NativeDocumentParser:
    """Shared evidence mapping; family-specific location and coverage hooks stay separate."""

    def __init__(self, engine: NativeEngine, sink: ArtifactSink):
        self.engine, self.sink = engine, sink

    def locations(self, source, item, raw_artifact, document):
        return [DocumentNode(artifact_id=raw_artifact.id, precision="derived_exact", pointer=item.pointer)]

    def finalize(self, source, document, blocks, coverage, issues):
        return None

    def parse(self, source: Source, path: Path) -> ParseResult:
        document = self.engine.convert(source, path)
        upstream = self.sink.put(json.dumps(document.payload, ensure_ascii=False, allow_nan=False).encode(),
                                 "engine_result", "application/json")
        artifacts = [Artifact(id=source.id, role="source", media_type=source.media_type,
                              sha256=source.sha256, size_bytes=source.size_bytes), upstream]
        blocks = []
        issues = list(document.issues)
        for index, item in enumerate(document.items):
            data = dict(item.data)
            if item.image is not None:
                asset = self.sink.put(item.image, "derived", item.image_media_type)
                if asset.id not in {a.id for a in artifacts}:
                    artifacts.append(asset)
                data["image_artifact_id"] = asset.id
            locations = self.locations(source, item, upstream, document)
            # Location hooks may add normalized source mappings to the item data.
            data.update(item.data)
            blocks.append(Block(id=f"content-{index}", kind=item.kind, text=item.text, data=data, locators=locations))
        coverage = [Coverage(unit_id="document", status="completed")]
        if any(item.kind == "image" for item in document.items):
            issues.append(Issue(code="images_not_recognized", severity="warning",
                                message="Image bytes are retained without OCR or visual interpretation"))
        if not document.successful:
            issues.append(Issue(code="engine_incomplete", message="Upstream conversion did not complete", severity="error"))
            coverage[0] = Coverage(unit_id="document", status="failed", issue_codes=["engine_incomplete"])
        self.finalize(source, document, blocks, coverage, issues)
        errors = any(i.severity == "error" for i in issues)
        status = ("partial" if blocks else "failed") if errors else "completed"
        return ParseResult(schema_version=SCHEMA_VERSION, source=source, status=status,
                           engine="docling-slim/2.139.0", artifacts=artifacts, blocks=blocks,
                           coverage=coverage, issues=issues)
