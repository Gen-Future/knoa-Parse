from pathlib import Path

from knoa_parse.core.json_value import read_json
from knoa_parse.core.models import Artifact, Block, Coverage, ParseResult, SCHEMA_VERSION, Source, StructuredNode


class JsonParser:
    def parse(self, source: Source, path: Path) -> ParseResult:
        # Retain the raw source artifact; root pointer preserves scalar/array/object values.
        value = read_json(path.read_bytes().decode("utf-8-sig"))
        return ParseResult(
            schema_version=SCHEMA_VERSION, source=source, status="completed", engine="knoa-json/1",
            artifacts=[Artifact(id=source.id, role="source", media_type=source.media_type,
                                sha256=source.sha256, size_bytes=source.size_bytes)],
            blocks=[Block(id="json-root", kind="structured", data={"value": value},
                          locators=[StructuredNode(artifact_id=source.id, precision="source_exact", pointer="")])],
            coverage=[Coverage(unit_id="document", status="completed")], issues=[],
        )
