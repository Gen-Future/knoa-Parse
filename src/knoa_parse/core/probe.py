"""Deterministic probing; never execute content or use a local classifier model."""
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from .errors import ParseError
from .json_value import read_json

NATIVE_FORMATS = {".txt": "text/plain", ".json": "application/json"}
OFFICE = {
    "word/document.xml": (".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "ppt/presentation.xml": (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "xl/workbook.xml": (".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}


def probe(path: Path, filename: str, max_entries: int = 10000, max_unpacked: int = 200_000_000) -> str:
    suffix = Path(filename).suffix.lower()
    with path.open("rb") as stream:
        head = stream.read(16)
    detected = None
    if head.startswith(b"%PDF-"):
        detected = (".pdf", "application/pdf")
    elif head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
        try:
            with ZipFile(path) as z:
                entries = z.infolist()
                if len(entries) > max_entries or sum(i.file_size for i in entries) > max_unpacked:
                    raise ParseError("resource_limit", "Container exceeds the configured budget", 413)
                matches = [v for k, v in OFFICE.items() if k in z.namelist()]
                if len(matches) != 1 or "[Content_Types].xml" not in z.namelist():
                    raise ParseError("unsupported_format", "Unrecognized or ambiguous ZIP container")
                detected = matches[0]
        except BadZipFile as exc:
            raise ParseError("invalid_container", "Invalid ZIP container") from exc
    if detected:
        if suffix != detected[0]:
            raise ParseError("format_conflict", "Filename conflicts with content signature")
        return detected[1]
    if suffix not in NATIVE_FORMATS:
        raise ParseError("unsupported_format", "This file format is not enabled")
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ParseError("invalid_encoding", "Initial text support requires UTF-8") from exc
    if "\x00" in text:
        raise ParseError("format_conflict", "Binary content cannot be treated as text")
    if suffix == ".json":
        read_json(text)
    return NATIVE_FORMATS[suffix]
