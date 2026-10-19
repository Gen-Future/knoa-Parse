import argparse
import json
import os
import sys
import time
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store

from .runtime import capabilities, make_store
from .worker import run_once


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="knoa-parse")
    parser.add_argument("--data-dir", type=Path, default=Path(os.getenv("KNOA_PARSE_DATA_DIR", ".local/knoa-parse")))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    parse = sub.add_parser("parse")
    parse.add_argument("file", type=Path)
    parse.add_argument("--timeout", type=float, default=30)
    for name in ("status", "result", "cancel"):
        sub.add_parser(name).add_argument("job_id")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    exit_code = 0
    try:
        if args.command == "capabilities":
            output = capabilities()
        else:
            store = make_store(Settings(args.data_dir, job_timeout_seconds=getattr(args, "timeout", 30)))
            if args.command == "parse":
                with args.file.open("rb") as stream:
                    source = store.ingest(stream, args.file.name)
                job = store.create_job(source.id)
                run_once(store, job["id"])
                state = store.job(job["id"])
                if state["state"] not in {"succeeded", "partial", "failed"} or not state["result_artifact_id"]:
                    error = state["error"] or {"code": state["state"], "message": "Task did not complete"}
                    raise ParseError(error["code"], error["message"])
                output = store.result(job["id"]).model_dump(mode="json")
                exit_code = {"succeeded": 0, "partial": 3, "failed": 2}[state["state"]]
            elif args.command == "worker":
                while True:
                    worked = run_once(store)
                    if args.once:
                        return 0
                    if not worked:
                        time.sleep(0.25)
            elif args.command == "result":
                output = store.result(args.job_id).model_dump(mode="json")
            elif args.command == "cancel":
                output = store.cancel(args.job_id)
            else:
                output = store.job(args.job_id)
        print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))
        return exit_code
    except ParseError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": exc.message}}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_input", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
