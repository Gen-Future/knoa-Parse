"""Composition root: format implementations are registered here, not in core."""
from knoa_parse.parsers.structured.parser import JsonParser
from knoa_parse.parsers.text.parser import TextParser
from dataclasses import replace

from knoa_parse.engines.docling import DoclingEngine, MIMES, dependency_status
from knoa_parse.core.store import Store
from knoa_parse.core.errors import ParseError
from knoa_parse.core.text_model import TextModelProvider

PARSERS = {"text/plain": TextParser(), "application/json": JsonParser()}
ACCEPTED_EXTENSIONS = {".txt", ".json", *MIMES.values()}


def make_store(settings):
    if dependency_status()["passed"]:
        settings = replace(settings, accepted_media_types=tuple(dict.fromkeys((*settings.accepted_media_types, *MIMES))))
    return Store(settings)


def get_parser(media_type, sink):
    if media_type in PARSERS:
        return PARSERS[media_type]
    if not dependency_status()["passed"]:
        raise ParseError("engine_not_enabled", "Install and audit the documents group before parsing")
    from knoa_parse.parsers.document.parser import WordParser
    from knoa_parse.parsers.presentation.parser import PresentationParser
    from knoa_parse.parsers.spreadsheet.parser import SpreadsheetParser
    from knoa_parse.parsers.pdf.parser import PdfParser
    from knoa_parse.processors.office.workbook import ExcelFields

    engine = DoclingEngine()
    constructors = {".docx": lambda: WordParser(engine, sink),
                    ".pptx": lambda: PresentationParser(engine, sink),
                    ".xlsx": lambda: SpreadsheetParser(engine, sink, ExcelFields()),
                    ".pdf": lambda: PdfParser(engine, sink)}
    return constructors[MIMES[media_type]]()


def capabilities(text_provider: TextModelProvider | None = None) -> dict:
    available = dependency_status()["passed"]
    formats = [{"extension": ".txt", "target": "native_extract", "encoding": "UTF-8"},
               {"extension": ".json", "target": "native_extract", "encoding": "UTF-8"}]
    if available:
        formats.extend({"extension": ext, "target": "native_extract"} for ext in MIMES.values())
    return {
        "schema_version": "0.2.0-draft.1",
        "formats": formats,
        "external_capabilities": [text_provider.describe()] if text_provider is not None else [],
        "document_engine": {"name": "docling", "enabled": available,
                            "reason": "Audited native paths only" if available else "Documents dependency audit failed"},
        "local_model_inference": False,
    }
