import argparse
import json
import os
from pathlib import Path

from knoa_parse.core.settings import Settings
from knoa_parse.core.errors import ParseError
from knoa_parse.core.store import Store

from . import execute


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("job_id")
    parser.add_argument("output", type=Path)
    parser.add_argument("max_result_bytes", type=int)
    args = parser.parse_args()
    if os.name != "nt":
        import resource

        resource.setrlimit(resource.RLIMIT_FSIZE, (args.max_result_bytes, args.max_result_bytes))
    try:
        execute(Store(Settings(args.data_dir, max_result_bytes=args.max_result_bytes), read_only=True), args.job_id, args.output)
    except ParseError as exc:
        args.output.write_text(json.dumps({"error": {"code": exc.code, "message": exc.message}}), encoding="utf-8")


if __name__ == "__main__":
    main()
