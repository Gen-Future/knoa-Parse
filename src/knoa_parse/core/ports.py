from pathlib import Path
from typing import Protocol

from .models import ParseResult, Source


class Parser(Protocol):
    def parse(self, source: Source, path: Path) -> ParseResult: ...
