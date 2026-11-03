"""Generate the current contract without rewriting older drafts."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from knoa_parse.core.models import ParseResult, SCHEMA_VERSION


def schema():
    value = ParseResult.model_json_schema()
    value["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    value["$id"] = f"https://knoa.dev/contracts/parse/{SCHEMA_VERSION}/parse-result.schema.json"
    return value


if __name__ == "__main__":
    path = ROOT / "contracts" / ("v" + SCHEMA_VERSION) / "parse-result.schema.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
