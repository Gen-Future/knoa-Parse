from pathlib import Path

from knoa_parse.core.models import Artifact, Block, Coverage, ParseResult, SCHEMA_VERSION, Source, TextSpan


class TextParser:
    def parse(self, source: Source, path: Path) -> ParseResult:
        # read_bytes preserves CRLF; offsets count Unicode code points of the original text.
        text = path.read_bytes().decode("utf-8")
        blocks = []
        if text:
            blocks.append(Block(
                id="text-1", kind="text", text=text,
                locators=[TextSpan(artifact_id=source.id, precision="source_exact", start=0, end=len(text))],
            ))
        return ParseResult(
            schema_version=SCHEMA_VERSION, source=source, status="completed", engine="knoa-text/1",
            artifacts=[Artifact(id=source.id, role="source", media_type=source.media_type,
                                sha256=source.sha256, size_bytes=source.size_bytes)],
            blocks=blocks, coverage=[Coverage(unit_id="document", status="completed")], issues=[],
        )
