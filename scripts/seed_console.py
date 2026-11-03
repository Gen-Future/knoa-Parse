"""Opt-in, real parser results for a separate synthetic console preview workspace."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "evals")]

from m2_fixtures import make_fixtures
from knoa_parse.apps.runtime import capabilities, make_store
from knoa_parse.apps.worker import run_once
from knoa_parse.core.settings import Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".local/console-preview/data")
    args = parser.parse_args()
    if not capabilities()["document_engine"]["enabled"]:
        parser.error("Preview inputs require the audited documents group")
    store = make_store(Settings(args.data_dir))
    if store.list_jobs(1)["items"]:
        parser.error("Choose an empty preview workspace; existing jobs will not be overwritten")
    fixtures = args.data_dir.parent / "fixtures"
    make_fixtures(fixtures)
    cases = [("mixed.pdf", "行业研究扫描件（合成）.pdf", True),
             ("broken.pdf", "损坏的资料（合成）.pdf", True),
             ("formulas.xlsx", "纯公式测算（合成）.xlsx", True),
             ("complex.pptx", "产品演示与图表（合成）.pptx", True),
             ("types.xlsx", "年度预算与测算（合成）.xlsx", True),
             ("cjk.pdf", "中文双栏研究（合成）.pdf", True),
             ("unicode.txt", "等待执行的笔记（合成）.txt", False),
             ("complex.docx", "中文研究记录（合成）.docx", True)]
    for filename, display_name, execute in cases:
        with (fixtures / filename).open("rb") as stream:
            source = store.ingest(stream, display_name)
        job = store.create_job(source.id)
        if execute:
            run_once(store, job["id"])
    print(f"Created {len(cases)} synthetic jobs through the real parser; one remains queued. Data: {args.data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
