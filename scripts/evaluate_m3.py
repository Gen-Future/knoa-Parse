"""Offline M3 composition demonstration, explicitly NOT real-service acceptance."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "evals")]

from m3_fixtures import ScriptedDocumentProvider, fixture
from knoa_parse.enrichment.document import analyze_pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/m3-dry-run")
    args = parser.parse_args()
    native, pages = fixture()
    provider = ScriptedDocumentProvider()
    report = analyze_pages(native, list(reversed(pages)), provider, dry_run=True)
    assert report.dry_run and report.status == "partial"
    assert [o.status for o in report.outcomes] == ["completed", "failed"]
    assert report.blocks[0].locators[0].bbox == [60.0, 160.0, 300.0, 320.0]
    assert report.blocks[0].context_block_ids == ["heading"]
    assert len(provider.calls) == 2 and report.total_tokens is None
    assert native.status == "partial" and len(native.blocks) == 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "report.json"
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"dry_run": True, "checks_passed": True, "real_service_verified": False, "report": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
