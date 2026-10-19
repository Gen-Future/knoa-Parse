import hashlib
from pathlib import Path

from .errors import ParseError
from .models import Artifact


class StagedArtifacts:
    """Task-local artifacts; only the lease-owning parent can publish them."""

    def __init__(self, directory: Path, max_bytes: int):
        self.directory, self.max_bytes = directory, max_bytes
        self.total = 0
        self.directory.mkdir(parents=True, exist_ok=True)

    def put(self, raw: bytes, role: str, media_type: str) -> Artifact:
        digest = hashlib.sha256(raw).hexdigest()
        destination = self.directory / digest
        if not destination.exists():
            if self.total + len(raw) > self.max_bytes:
                raise ParseError("resource_limit", "Document artifacts exceed the output budget", 413)
            destination.write_bytes(raw)
            self.total += len(raw)
        return Artifact(id=f"{role}-{digest}", role=role, media_type=media_type,
                        sha256=digest, size_bytes=len(raw))
