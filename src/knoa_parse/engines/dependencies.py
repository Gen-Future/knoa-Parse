"""Audit the installed project dependency closure without importing optional engines."""
import importlib.metadata as metadata
import json
import re
from collections import deque
from pathlib import Path
import tomllib

from packaging.requirements import Requirement

FORBIDDEN = re.compile(
    r"^(torch(?:vision|audio)?|transformers|onnxruntime.*|huggingface-hub|modelscope|"
    r"lightrag.*|mineru.*|raganything|magika|spacy.*|easyocr|rapidocr.*|paddle.*|"
    r"faster-whisper|openai-whisper|sentence-transformers|docling-ibm-models|"
    r"ctranslate2|llama-cpp-python|nvidia-.*|vllm)$"
)
DOCUMENT_ROOT = "docling-slim[convert-core,format-docx,format-pptx,format-xlsx,format-pdf-docling]==2.139.0"


def audit_lock(path: Path):
    if not path.is_file():
        return {"passed": False, "issues": [{"code": "lock_missing"}]}
    packages = tomllib.loads(path.read_text(encoding="utf-8"))["package"]
    forbidden = [p["name"] for p in packages if FORBIDDEN.fullmatch(p["name"])]
    return {"passed": not forbidden, "package_records": len(packages), "forbidden": forbidden}


def audit(roots):
    pending = deque((Requirement(root), None) for root in roots)
    visited, packages, issues = set(), {}, []
    while pending:
        req, parent = pending.popleft()
        name = re.sub(r"[-_.]+", "-", req.name).lower()
        if FORBIDDEN.fullmatch(name):
            issues.append({"code": "forbidden_dependency", "name": name, "parent": parent})
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            issues.append({"code": "missing_dependency", "name": name, "parent": parent})
            continue
        if req.specifier and not req.specifier.contains(dist.version, prereleases=True):
            issues.append({"code": "version_mismatch", "name": name, "installed": dist.version, "required": str(req.specifier)})
        provided = {re.sub(r"[-_.]+", "-", e).lower() for e in dist.metadata.get_all("Provides-Extra", [])}
        if not req.extras <= provided:
            issues.append({"code": "unknown_extra", "name": name, "extras": sorted(req.extras - provided)})
        packages[name] = dist.version
        for extra in {"", *req.extras}:
            key = (name, extra)
            if key in visited:
                continue
            visited.add(key)
            for raw in dist.requires or []:
                child = Requirement(raw)
                if child.marker is None or child.marker.evaluate({"extra": extra}):
                    pending.append((child, name))
    return {"passed": not issues, "packages": dict(sorted(packages.items())), "issues": issues}
