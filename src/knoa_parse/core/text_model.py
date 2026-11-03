"""Supplier-neutral synchronous text generation port; separate from extraction evidence."""
from typing import Literal, Protocol

from pydantic import Field

from .errors import ProviderError
from .models import Model


class TextRequest(Model):
    prompt: str = Field(min_length=1, max_length=32000)
    system: str = Field(default="You are a helpful assistant.", max_length=4000)
    max_tokens: int = Field(default=1024, ge=1, le=4096)


class TokenUsage(Model):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class TextResponse(Model):
    provider: str
    model: str
    text: str
    finish_reason: str
    usage: TokenUsage
    request_id: str | None = None
    acquisition: Literal["inferred"] = "inferred"


class TextModelProvider(Protocol):
    def describe(self) -> dict: ...

    def complete(self, request: TextRequest) -> TextResponse: ...
