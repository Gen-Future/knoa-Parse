from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_source_bytes: int = 10 * 1024 * 1024
    job_timeout_seconds: float = 30.0
    max_result_bytes: int = 20 * 1024 * 1024
    accepted_media_types: tuple[str, ...] = ("text/plain", "application/json")

    def __post_init__(self):
        if min(self.max_source_bytes, self.max_result_bytes, self.job_timeout_seconds) <= 0:
            raise ValueError("Resource limits must be positive")
