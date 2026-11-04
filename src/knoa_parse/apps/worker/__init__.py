"""Single-host worker, with subprocess timeout and cancellation."""
import os
import json
import signal
import subprocess
import sys
import time
import shutil
from pathlib import Path

from knoa_parse.core.errors import ParseError
from knoa_parse.core.models import ParseResult
from knoa_parse.core.store import Store
from knoa_parse.core.artifacts import StagedArtifacts


def deny_network(event, args):
    if event in {"socket.connect", "socket.connect_ex", "socket.sendto", "socket.getaddrinfo",
                 "socket.gethostbyname", "socket.gethostbyaddr", "os.system"}:
        raise PermissionError("Native extraction cannot use network or launch subprocesses")
    if event == "subprocess.Popen":
        executable = args[0] if args else ""
        name = os.path.basename(str(executable)).lower()
        if name not in {"ffmpeg", "ffmpeg.exe", "ffprobe", "ffprobe.exe"}:
            raise PermissionError("Native extraction cannot launch this subprocess")


def execute(store: Store, job_id: str, output: Path):
    sys.addaudithook(deny_network)
    from knoa_parse.apps.runtime import get_parser

    job = store.job(job_id)
    source = store.source(job["source_id"])
    path = store.verify_source(source)
    sink = StagedArtifacts(output.with_suffix(".artifacts"), store.settings.max_result_bytes)
    result = get_parser(source.media_type, sink).parse(source, path)
    payload = result.model_dump_json().encode("utf-8")
    if len(payload) + sink.total > store.settings.max_result_bytes:
        raise ParseError("resource_limit", "Result and artifacts exceed the output budget", 413)
    output.write_bytes(payload)


def run_once(store: Store, job_id: str | None = None) -> bool:
    claimed = store.claim(job_id)
    if claimed is None:
        return False
    identifier, token = claimed
    output = store.root / "staging" / (token + ".json")
    process = None
    try:
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(p) for p in sys.path if p))
        process = subprocess.Popen(
            [sys.executable, "-m", "knoa_parse.apps.worker", str(store.root), identifier, str(output),
             str(store.settings.max_result_bytes)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=os.name != "nt",
        )
        deadline = time.monotonic() + store.settings.job_timeout_seconds
        while process.poll() is None:
            if store.job(identifier)["state"] == "cancelled":
                _stop(process)
                return True
            if time.monotonic() >= deadline:
                _stop(process)
                raise ParseError("execution_timeout", "Task exceeded its execution budget")
            if output.exists() and output.stat().st_size > store.settings.max_result_bytes:
                _stop(process)
                raise ParseError("resource_limit", "Result exceeded its size budget")
            time.sleep(0.02)
        if process.returncode != 0 or not output.exists():
            raise ParseError("execution_failed", "Parser process failed; source was not accepted as complete")
        if output.stat().st_size > store.settings.max_result_bytes:
            raise ParseError("resource_limit", "Result exceeded its size budget")
        payload = output.read_bytes()
        decoded = json.loads(payload)
        if "error" in decoded:
            raise ParseError(decoded["error"]["code"], decoded["error"]["message"])
        result = ParseResult.model_validate_json(payload)
        store.finish(identifier, token, result, staged=output.with_suffix(".artifacts"))
    except KeyboardInterrupt:
        store.cancel(identifier)
        raise
    except ParseError as exc:
        store.fail(identifier, token, exc.code, exc.message)
    except Exception:
        store.fail(identifier, token, "execution_failed", "Result validation or task execution failed")
    finally:
        if process is not None and process.poll() is None:
            _stop(process)
        output.unlink(missing_ok=True)
        shutil.rmtree(output.with_suffix(".artifacts"), ignore_errors=True)
    return True


def _stop(process):
    if process.poll() is None:
        try:
            if os.name == "nt":
                # Native extraction forbids spawning descendants through the audit guard.
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()
