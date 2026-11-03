"""Run the authored M2 corpus and retain artifacts plus a semantic failure report."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "evals")]

from m2_acceptance import evaluate


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / ".local/m2-acceptance")
    parser.add_argument("--base-only", action="store_true", help="Explicitly restrict evaluation to TXT/JSON")
    args = parser.parse_args()
    report = evaluate(args.output_dir, args.base_only)
    print(json.dumps({"passed": report["passed"], "scope": report["scope"],
                      "passed_count": report["passed_count"], "case_count": report["case_count"],
                      "failures": [o for o in report["cases"] if not o["passed"]],
                      "report": str(args.output_dir / "report.json")}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
