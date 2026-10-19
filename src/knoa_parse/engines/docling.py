"""One explicitly model-free Docling integration. Third-party types stop here."""
import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from knoa_parse.core.documents import EngineDocument, EngineItem
from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import Issue, Source

from .dependencies import DOCUMENT_ROOT, audit

MIMES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


@lru_cache(maxsize=1)
def dependency_status():
    return audit([DOCUMENT_ROOT])


class DoclingEngine:
    def convert(self, source: Source, path: Path) -> EngineDocument:
        if not dependency_status()["passed"]:
            raise ParseError("engine_not_enabled", "The documents dependency group has not passed audit")
        from docling.datamodel.base_models import DocumentStream, InputFormat
        from docling.datamodel.pipeline_options import ConvertPipelineOptions, NativePdfPipelineOptions
        from docling.document_converter import (
            DocumentConverter, ExcelFormatOption, NativePdfFormatOption,
            PowerpointFormatOption, WordFormatOption,
        )

        options = dict(enable_remote_services=False, allow_external_plugins=False,
                       do_picture_classification=False, do_picture_description=False,
                       do_chart_extraction=False, document_timeout=20)
        formats = {
            ".docx": (InputFormat.DOCX, WordFormatOption(pipeline_options=ConvertPipelineOptions(**options))),
            ".pptx": (InputFormat.PPTX, PowerpointFormatOption(pipeline_options=ConvertPipelineOptions(**options))),
            ".xlsx": (InputFormat.XLSX, ExcelFormatOption(pipeline_options=ConvertPipelineOptions(**options))),
            ".pdf": (InputFormat.PDF, NativePdfFormatOption(pipeline_options=NativePdfPipelineOptions(
                **options, generate_page_images=False, generate_picture_images=True, parser_threads=2))),
        }
        suffix = MIMES[source.media_type]
        selected, configuration = formats[suffix]
        converter = DocumentConverter(allowed_formats=[selected], format_options={selected: configuration})
        converted = converter.convert(DocumentStream(name=source.filename, stream=BytesIO(path.read_bytes())),
                                      raises_on_error=False, max_num_pages=100)
        if converted.document is None:
            raise ParseError("conversion_failed", "The document could not be converted")
        raw = converted.document.export_to_dict()
        lookup = {}
        for key in ("groups", "texts", "tables", "pictures", "key_value_items", "form_items"):
            for item in raw.get(key, []):
                lookup[item["self_ref"]] = item
        for key in ("body", "furniture"):
            if key in raw:
                lookup[raw[key]["self_ref"]] = raw[key]
        ordered, seen = [], set()

        def walk(pointer):
            if pointer in seen:
                return
            seen.add(pointer)
            node = lookup.get(pointer)
            if node is None:
                return
            ordered.append(node)
            for ref in node.get("children", []):
                walk(ref["$ref"])

        walk("#/body")
        walk("#/furniture")
        for pointer in lookup:  # Preserve content outside default body/furniture layers.
            walk(pointer)
        items, issues = [], []
        for node in ordered:
            pointer = node["self_ref"]
            if not pointer.startswith(("#/texts/", "#/tables/", "#/pictures/")):
                continue
            data = {"label": node.get("label", ""), "content_role": node.get("content_layer", "body")}
            kind = "text"
            text = node.get("text")
            image, image_type = None, None
            if pointer.startswith("#/tables/"):
                kind = "table"
                table = node["data"]
                data["rows"], data["columns"] = table["num_rows"], table["num_cols"]
                data["cells"] = [{"text": c["text"], "row": c["start_row_offset_idx"],
                                  "column": c["start_col_offset_idx"], "row_span": c["row_span"],
                                  "column_span": c["col_span"], "column_header": c.get("column_header", False)}
                                 for c in table["table_cells"]]
            elif pointer.startswith("#/pictures/"):
                kind = "image"
                image_info = node.get("image", {})
                uri = image_info.get("uri", "")
                if uri.startswith("data:image/") and ";base64," in uri:
                    image_type = uri.split(";", 1)[0][5:]
                    image = base64.b64decode(uri.split(",", 1)[1], validate=True)
                    data["size"] = image_info.get("size")
                else:
                    issues.append(Issue(code="image_unavailable", message="An embedded image has no retained bytes", severity="error"))
            locations = []
            for prov in node.get("prov", []):
                box = prov["bbox"]
                locations.append({"page": prov["page_no"], "bbox": [box["l"], box["t"], box["r"], box["b"]],
                                  "origin": "top_left" if box["coord_origin"] == "TOPLEFT" else "bottom_left"})
            items.append(EngineItem(pointer, kind, text, data, locations, image, image_type))
        if raw.get("key_value_items") or raw.get("form_items"):
            issues.append(Issue(code="unmapped_content", message="Form content is retained only in the upstream artifact", severity="error"))
        for error in converted.errors:
            issues.append(Issue(code="engine_reported_error", message=error.error_message, severity="error"))
        successful = converted.status.value == "success"
        return EngineDocument(raw, items, sorted(int(p) for p in raw.get("pages", {})), issues, successful)
