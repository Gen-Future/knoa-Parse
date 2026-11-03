"""Shared validated settings and bounded HTTP transport for remote text protocols."""
import json
import math
import re
import socket
from http.client import HTTPException
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request

from knoa_parse.core.text_model import ProviderError


@dataclass(frozen=True)
class TextModelConfig:
    provider: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 60.0
    max_output_tokens: int = 4096
    max_input_chars: int = 36000
    max_response_bytes: int = 2 * 1024 * 1024
    enable_thinking: bool | None = None
    protocol: str = "openai"
    anthropic_version: str = "2023-06-01"

    def __post_init__(self):
        if any(not isinstance(value, str) for value in (self.provider, self.base_url, self.model, self.api_key)):
            raise ValueError("Provider identity, URL, model and credential must be strings")
        url = urlsplit(self.base_url)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.query or url.fragment):
            raise ValueError("Provider base_url must be an HTTPS URL without credentials, query or fragment")
        if not self.provider.strip() or len(self.provider) > 64:
            raise ValueError("Provider name must contain 1 to 64 characters")
        if self.protocol not in {"openai", "anthropic"}:
            raise ValueError("Protocol must be openai or anthropic")
        if not isinstance(self.anthropic_version, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", self.anthropic_version):
            raise ValueError("Invalid Anthropic API version")
        if self.protocol == "anthropic" and self.enable_thinking is not None:
            raise ValueError("enable_thinking is only supported by the OpenAI protocol adapter")
        if not self.api_key or any(not 33 <= ord(c) <= 126 for c in self.api_key):
            raise ValueError("Provider API key is missing or invalid")
        if not self.model.strip() or len(self.model) > 256:
            raise ValueError("Provider model is required (at most 256 characters)")
        if (type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 300):
            raise ValueError("Provider timeout must be within (0, 300] seconds")
        for value, limit in ((self.max_output_tokens, 4096), (self.max_input_chars, 36000),
                             (self.max_response_bytes, 8 * 1024 * 1024)):
            if type(value) is not int or not 0 < value <= limit:
                raise ValueError("Provider resource limit is invalid")
        if self.enable_thinking is not None and type(self.enable_thinking) is not bool:
            raise ValueError("enable_thinking must be boolean or null")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the authorization header to a redirect destination.
        return None


def post_json(c: TextModelConfig, opener, path: str, payload: dict, headers: dict):
    raw = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    req = Request(c.base_url.rstrip("/") + path, data=raw,
                  headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        # Exactly one attempt: a timed-out request may already have been billed.
        with opener.open(req, timeout=c.timeout_seconds) as response:
            body = response.read(c.max_response_bytes + 1)
            trace = response.headers.get("x-siliconcloud-trace-id") or response.headers.get("x-request-id") or response.headers.get("request-id")
    except HTTPError as exc:
        status = exc.code
        exc.close()
        code, message, public_status = {
            401: ("provider_authentication", "Model service rejected the credential", 502),
            402: ("provider_quota", "Model service quota or balance is insufficient", 502),
            403: ("provider_forbidden", "Model service denied access; check account and model permissions", 502),
            404: ("provider_model_unavailable", "Model or endpoint is unavailable", 502),
            429: ("provider_rate_limit", "Model service rate limit or quota exceeded", 429),
        }.get(status, ("provider_http_error", "Model service returned HTTP " + str(status), 502))
        raise ProviderError(code, message, public_status, retryable=status == 429 or status >= 500) from None
    except (TimeoutError, socket.timeout):
        raise ProviderError("provider_timeout", "Model service timed out; billing status may be unknown", 504, retryable=True) from None
    except URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ProviderError("provider_timeout", "Model service timed out; billing status may be unknown", 504, retryable=True) from None
        raise ProviderError("provider_unavailable", "Could not connect to model service", 503, retryable=True) from None
    except (OSError, HTTPException):
        raise ProviderError("provider_unavailable", "Could not connect to model service", 503, retryable=True) from None
    if len(body) > c.max_response_bytes:
        raise ProviderError("provider_response_limit", "Model response exceeds configured size limit")
    return body, trace
