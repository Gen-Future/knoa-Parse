"""Bounded stdout subprocess helper for media tools."""
from dataclasses import dataclass
import subprocess
from threading import Thread


@dataclass(frozen=True)
class BoundedProcessResult:
    returncode: int
    stdout: bytes


class BoundedProcessError(Exception):
    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


def run_bounded(command: list[str], *, timeout_seconds: float, max_output_bytes: int) -> BoundedProcessResult:
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, shell=False)
    except FileNotFoundError:
        raise BoundedProcessError("missing") from None
    except OSError:
        raise BoundedProcessError("unavailable") from None
    chunks: list[bytes] = []
    size = 0
    overflow = False

    def read_stdout():
        nonlocal size, overflow
        assert process.stdout is not None
        while True:
            chunk = process.stdout.read(64 * 1024)
            if not chunk:
                return
            if size + len(chunk) > max_output_bytes:
                overflow = True
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
                return
            chunks.append(chunk)
            size += len(chunk)

    reader = Thread(target=read_stdout, daemon=True)
    reader.start()
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.wait()
        reader.join(timeout=2)
        if process.stdout is not None:
            process.stdout.close()
        raise BoundedProcessError("timeout") from None
    reader.join(timeout=2)
    if reader.is_alive():
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.wait()
        if process.stdout is not None:
            process.stdout.close()
        raise BoundedProcessError("unavailable")
    if overflow:
        if process.stdout is not None:
            process.stdout.close()
        raise BoundedProcessError("limit")
    if process.stdout is not None:
        process.stdout.close()
    return BoundedProcessResult(process.returncode, b"".join(chunks))
