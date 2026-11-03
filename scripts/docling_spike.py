"""M0 acceptance entry: audit before import, then convert only explicit local fixtures."""
import argparse
import json
import hashlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from audit_dependencies import DOCUMENT_ROOT, audit
from knoa_parse.apps.worker import deny_network


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/docling-spike")
    args = parser.parse_args()
    report = {"candidate": DOCUMENT_ROOT, "python": sys.version.split()[0],
              "dependency_audit": audit([DOCUMENT_ROOT]), "cases": [],
              "status": "blocked", "conversion_is_full_acceptance": False}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if report["dependency_audit"]["passed"] and args.input:
        denied = []
        def guard(event, values):
            try:
                deny_network(event, values)
            except PermissionError:
                denied.append({"event": event, "command": values[1] if event == "subprocess.Popen" else None})
                raise
        sys.addaudithook(guard)
        started = time.monotonic()
        try:
            from knoa_parse.engines.docling import DoclingEngine
            from knoa_parse.core.models import Source
            from knoa_parse.core.probe import probe

            for index, path in enumerate(args.input):
                source_bytes = path.read_bytes()
                digest = hashlib.sha256(source_bytes).hexdigest()
                source = Source(id="fixture-" + digest, revision=digest, filename=path.name,
                                media_type=probe(path, path.name), sha256=digest, size_bytes=len(source_bytes))
                before = time.monotonic()
                converted = DoclingEngine().convert(source, path)
                case = {"filename": path.name, "sha256": digest,
                        "status": "success" if converted.successful else "incomplete",
                        "elapsed_seconds": time.monotonic() - before,
                        "items": len(converted.items), "issues": [i.code for i in converted.issues]}
                destination = args.output_dir / f"upstream-{index}.json"
                destination.write_text(json.dumps(converted.payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
                case["artifact"] = destination.name
                report["cases"].append(case)
            report["inference_modules_loaded"] = [m for m in sys.modules if m.split(".")[0] in
                {"torch", "transformers", "onnxruntime", "whisper", "huggingface_hub", "modelscope"}]
            report["status"] = "observed"
            report["note"] = "Conversion alone is not acceptance; compare structure, provenance and Excel semantics."
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = {"type": type(exc).__name__, "message": str(exc)}
        report["denied_network_or_process_events"] = denied
        def platform_probe(entry):
            command = entry["command"]
            if entry["event"] != "subprocess.Popen" or not isinstance(command, list):
                return False
            return command == ["uname", "-p"] or (
                len(command) == 3 and command[:2] == ["file", "-b"]
                and Path(command[2]).resolve() == Path(sys.executable).resolve()
            )
        # These calls remain blocked. Recognize harmless platform introspection separately.
        report["unexpected_denials"] = [entry for entry in denied if not platform_probe(entry)]
        if report["unexpected_denials"] or report.get("inference_modules_loaded") or any(c["status"] != "success" for c in report["cases"]):
            report["status"] = "failed"
        report["elapsed_seconds"] = time.monotonic() - started
        if sys.platform == "win32":
            report["process_peak_rss_bytes"] = None
            report["memory_measurement_note"] = "resource.getrusage is unavailable on Windows; peak RSS was not measured"
        else:
            import resource

            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            report["process_peak_rss_bytes"] = rss if sys.platform == "darwin" else rss * 1024
    elif not args.input:
        report["note"] = "Provide synthetic fixtures with --input after installing the audited documents group."
    (args.output_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
