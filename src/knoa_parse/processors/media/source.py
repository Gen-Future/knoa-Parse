"""Trusted media staging boundary kept out of core contracts."""
from dataclasses import dataclass
from pathlib import Path

from knoa_parse.core.media import MediaProbeInput


@dataclass(frozen=True)
class StagedMedia:
    identity: MediaProbeInput
    path: Path

    def __post_init__(self):
        if not isinstance(self.path, Path) or not self.path.is_file() or self.path.is_symlink():
            raise ValueError("A regular staged media path is required")

    @property
    def source_id(self) -> str:
        return self.identity.source_id

    @property
    def source_sha256(self) -> str:
        return self.identity.source_sha256

    @property
    def size_bytes(self) -> int:
        return self.identity.size_bytes
