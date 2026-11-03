"""Audit the installed project dependency closure without importing document engines."""
import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from knoa_parse.engines.dependencies import DOCUMENT_ROOT, FORBIDDEN, audit, audit_lock, metadata

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", action="store_true")
    parser.add_argument("--api", action="store_true")
    parser.add_argument("--video", action="store_true")
    args = parser.parse_args()
    roots = ["pydantic==2.13.1"] + ([DOCUMENT_ROOT] if args.documents else [])
    if args.api:
        roots += ["fastapi==0.135.3", "uvicorn==0.44.0"]
    if args.video:
        roots += ["scenedetect-headless==0.7.2"]
    result = audit(roots)
    result["lock_audit"] = audit_lock(Path(__file__).resolve().parents[1] / "uv.lock")
    result["passed"] = result["passed"] and result["lock_audit"]["passed"]
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
