import argparse
import json
import sys
import time
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.settings import Settings
from knoa_parse.core.store import Store

from .runtime import capabilities, make_store
from .worker import run_once
from .model_services import require_text_provider, text_provider_from_env
from .configuration import server_configuration
from knoa_parse.core.text_model import ProviderError, TextRequest


def main(argv=None) -> int:
    # CLI JSON is UTF-8 even when Windows redirects stdout using a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="knoa-parse")
    parser.add_argument("--data-dir", type=Path, default=server_configuration().data_dir)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("model-check")
    model_text = sub.add_parser("model-text")
    model_text.add_argument("file", type=Path)
    model_text.add_argument("--max-tokens", type=int, default=1024)
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
            output = capabilities(text_provider_from_env())
        elif args.command in {"model-check", "model-text"}:
            provider = require_text_provider(text_provider_from_env())
            if args.command == "model-check":
                request = TextRequest(prompt="Reply with exactly OK.", max_tokens=16)
            else:
                with args.file.open("rb") as stream:
                    raw = stream.read(128001)
                if len(raw) > 128000:
                    raise ParseError("resource_limit", "Model prompt file exceeds size limit", 413)
                request = TextRequest(prompt=raw.decode("utf-8"), max_tokens=args.max_tokens)
            output = provider.complete(request).model_dump(mode="json")
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
        error = {"code": exc.code, "message": exc.message}
        if isinstance(exc, ProviderError):
            error["retryable"] = exc.retryable
        print(json.dumps({"error": error}, ensure_ascii=False), file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": {"code": "invalid_input", "message": str(exc)}}, ensure_ascii=False), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
