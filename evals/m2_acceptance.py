"""Semantic M2 acceptance against authored expectations, through the real task/worker path."""
import hashlib
import json
import platform
import time
from pathlib import Path

from knoa_parse.apps.runtime import capabilities, make_store
from knoa_parse.apps.worker import run_once
from knoa_parse.core.errors import ParseError
from knoa_parse.core.settings import Settings

from m2_fixtures import make_fixtures

MANIFEST = Path(__file__).with_name("m2-cases.json")


def same(left, right):
    # Python's True == 1 must not conceal a change of JSON data type.
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def subset(actual, expected):
    return all(key in actual and same(actual[key], value) for key, value in expected.items())


def resolve_pointer(value, pointer):
    if pointer.startswith("#"):
        pointer = pointer[1:]
    if not pointer:
        return value
    if not pointer.startswith("/"):
        raise ValueError("Invalid JSON pointer")
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        value = value[int(token)] if isinstance(value, list) else value[token]
    return value


def check_result(case, result, store):
    """Return actionable mismatches. Expectations are never learned from this result."""
    failures = []
    def require(ok, description):
        if not ok:
            failures.append(description)

    require(result.status == case["expected"], f"status: expected {case['expected']}, observed {result.status}")
    artifacts = {}
    for artifact in result.artifacts:
        path, _ = store.artifact(artifact.id)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == artifact.sha256 and len(raw) == artifact.size_bytes,
                f"artifact digest/size mismatch: {artifact.role}")
        artifacts[artifact.id] = raw
    raw_source = artifacts[result.source.id]
    for block in result.blocks:
        data = block.data or {}
        for location in block.locators:
            try:
                raw = artifacts[location.artifact_id]
                if location.kind == "text_span":
                    text = raw.decode("utf-8")
                    require(location.end <= len(text) and text[location.start:location.end] == block.text,
                            f"{block.id}: source text span mismatch")
                elif location.kind == "structured_node":
                    resolved = resolve_pointer(json.loads(raw.decode("utf-8-sig")), location.pointer)
                    require(same(resolved, data.get("value")), f"{block.id}: JSON value/type mismatch")
                elif location.kind == "document_node" and location.precision == "derived_exact":
                    resolved = resolve_pointer(json.loads(raw), location.pointer)
                    require(isinstance(resolved, dict), f"{block.id}: derived node does not resolve to an object")
                    if block.kind == "text":
                        require(resolved.get("text") == block.text, f"{block.id}: upstream text mapping changed")
                elif location.kind == "sheet_range" and data.get("role") == "original_cell":
                    require(location.sheet == data["sheet"] and location.a1_range == data["address"],
                            f"{block.id}: original-cell locator mismatch")
                elif location.kind == "page_region":
                    dimensions = case.get("page_sizes", {}).get(str(location.page))
                    require(dimensions is not None, f"{block.id}: unexpected source page")
                    if dimensions:
                        left, top, right, bottom = location.bbox
                        require(0 <= left <= right <= dimensions[0] and 0 <= min(top, bottom) <= max(top, bottom) <= dimensions[1],
                                f"{block.id}: PDF region outside authored page dimensions")
                    require(location.unit == "pt" and location.precision == "source_exact", f"{block.id}: invalid PDF units/precision")
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                failures.append(f"{block.id}: locator resolution failed ({type(exc).__name__})")
        if data.get("role") == "native_chart":
            require(all(loc.precision == "derived_exact" for loc in block.locators),
                    f"{block.id}: reconstructed chart cells must not invent original sheet addresses")
        if block.kind == "image":
            require(data.get("image_artifact_id") in artifacts, f"{block.id}: image bytes were not retained")
    for check in case.get("checks", []):
        kind = check["type"]
        if kind == "text_exact":
            actual = [b.text for b in result.blocks]
            require(same(actual, [check["value"]]) and raw_source.decode("utf-8") == check["value"], "original text/BOM/newlines changed")
        elif kind == "json_exact":
            require(len(result.blocks) == 1 and same(result.blocks[0].data["value"], check["value"]), "JSON content or native types changed")
        elif kind == "text_count":
            require(sum(b.text == check["value"] for b in result.blocks) == check["count"], f"text count mismatch: {check['value']}")
        elif kind == "text_absent":
            require(all(check["value"] not in (b.text or "") for b in result.blocks), f"unexpected deleted text: {check['value']}")
        elif kind == "table_cell":
            cells = [c for b in result.blocks if b.kind == "table" for c in (b.data or {}).get("cells", [])]
            require(sum(subset(c, check["fields"]) for c in cells) == check["count"], f"table cell/span mismatch: {check['fields']}")
        elif kind == "slide_text":
            require(sum(b.text == check["value"] and subset(b.data or {}, {"slide_indices": [check["slide"]], "content_role": check["role"]})
                        for b in result.blocks) == 1, f"slide/role association mismatch: {check['value']}")
        elif kind == "chart_cells":
            charts = [b for b in result.blocks if (b.data or {}).get("role") == "native_chart"]
            require(any(set(check["texts"]) <= {c["text"] for c in b.data["cells"]} for b in charts), "native chart series/categories/values missing")
        elif kind == "cell":
            cells = [b for b in result.blocks if subset(b.data or {}, {"role": "original_cell", "sheet": check["sheet"], "address": check["address"]})]
            require(len(cells) == 1 and subset(cells[0].data, check["fields"]), f"original cell mismatch: {check['sheet']}!{check['address']}")
        elif kind == "sheet_order":
            metadata = [b for b in result.blocks if b.id == "workbook-metadata"]
            require(len(metadata) == 1 and [s["name"] for s in metadata[0].data["sheets"]] == check["names"], "workbook sheet order changed")
        elif kind == "sheet_table":
            require(any(b.kind == "table" and any(c["text"] == check["contains"] for c in (b.data or {}).get("cells", []))
                        and any(loc.kind == "sheet_range" and loc.sheet == check["sheet"] for loc in b.locators) for b in result.blocks),
                    "table attached to wrong sheet after blank/chart sheet")
        elif kind == "pdf_text":
            regions = [loc for b in result.blocks if b.text == check["value"] for loc in b.locators if loc.kind == "page_region" and loc.page == check["page"]]
            outer = check["region"]
            require(len(regions) == 1 and regions[0].origin == "bottom_left" and
                    outer[0] <= regions[0].bbox[0] <= regions[0].bbox[2] <= outer[2] and
                    outer[3] <= regions[0].bbox[3] <= regions[0].bbox[1] <= outer[1], f"PDF text/page/rotation mismatch: {check['value']}")
        elif kind == "image_count":
            require(sum(b.kind == "image" for b in result.blocks) == check["count"], "image count mismatch")
        elif kind == "issue":
            require(any(i.code == check["code"] and i.severity == check["severity"] for i in result.issues), f"missing issue: {check['code']}")
        elif kind == "coverage":
            require(any(c.unit_id == check["unit"] and c.status == check["status"] for c in result.coverage), f"coverage mismatch: {check['unit']}")
        else:
            raise ValueError(f"Unknown golden check: {kind}")
    return failures


def evaluate(directory: Path, base_only: bool = False):
    directory.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    available = capabilities()["document_engine"]["enabled"]
    make_fixtures(directory / "fixtures", documents=available and not base_only)
    store = make_store(Settings(directory / "data"))
    observations = []
    for case in manifest["cases"]:
        observation = {"id": case["id"], "file": case["file"], "passed": False, "failures": []}
        if case.get("documents") and base_only:
            continue
        observations.append(observation)
        if case.get("documents") and not available:
            observation.update(status="blocked", failures=["Audited documents group is not installed"])
            continue
        path = directory / "fixtures" / case["file"]
        raw = path.read_bytes()
        observation["input_sha256"] = hashlib.sha256(raw).hexdigest()
        started = time.monotonic()
        try:
            with path.open("rb") as stream:
                try:
                    source = store.ingest(stream, path.name)
                except ParseError as exc:
                    observation.update(status="ingest_rejected", error_code=exc.code)
                    observation["passed"] = case.get("ingest_error") == exc.code
                    if not observation["passed"]:
                        observation["failures"].append(f"Unexpected ingest error: {exc.code}")
                    continue
            if case.get("ingest_error"):
                observation["failures"].append("Expected ingest rejection; input was accepted")
                continue
            job = store.create_job(source.id)
            observation["job_id"] = job["id"]
            run_once(store, job["id"])
            state = store.job(job["id"])
            observation["status"] = state["state"]
            if state["result_artifact_id"]:
                result = store.result(job["id"])
                observation.update(result_artifact_id=state["result_artifact_id"], engine=result.engine,
                                   result_status=result.status, issues=[i.code for i in result.issues], block_count=len(result.blocks))
                observation["failures"].extend(check_result(case, result, store))
                observation["passed"] = not observation["failures"]
            else:
                observation["error_code"] = (state["error"] or {}).get("code")
                observation["passed"] = state["state"] == "failed" and observation["error_code"] == case.get("job_error")
                if not observation["passed"]:
                    observation["failures"].append(f"No result: {state['error']}")
        except Exception as exc:
            observation["failures"].append(f"{type(exc).__name__}: {exc}")
        finally:
            observation["elapsed_seconds"] = time.monotonic() - started
    report = {"suite": "m2-authored-v1", "scope": "base-only" if base_only else "all-six-formats",
              "platform": platform.system(), "python": platform.python_version(),
              "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
              "passed": all(o["passed"] for o in observations), "cases": observations,
              "case_count": len(observations), "passed_count": sum(o["passed"] for o in observations),
              "limitations": ["Synthetic content only; not a real-document accuracy score", "PDF test CMap is authored; font rendering fidelity is not evaluated"]}
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report
