"""Vendor-neutral external ASR JSON transport.

This is an adapter seam and an offline-testable protocol, not a speech engine
and not a claim that any particular ASR vendor is enabled.
"""
import base64
import hashlib
import json
import math
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from knoa_parse.core.asr import (
    AsrCapability,
    AsrRequest,
    AsrResponse,
    AsrUsage,
    TranscriptSegment,
    TranscriptWord,
)
from knoa_parse.core.errors import ProviderError


class AsrProviderError(ProviderError):
    """Stable, sanitized error for an external ASR service."""


@dataclass(frozen=True)
class HttpAsrConfig:
    provider: str
    base_url: str
    api_key: str = field(repr=False)
    version: str = "http-asr-v1"
    timeout_seconds: float = 60.0
    max_response_bytes: int = 16 * 1024 * 1024
    max_request_bytes: int = 32 * 1024 * 1024
    max_segment_bytes: int = 20 * 1024 * 1024
    max_segment_ms: int = 30 * 60 * 1000
    allow_local_http: bool = False

    def __post_init__(self):
        if not isinstance(self.base_url, str) or any(ord(c) < 33 or ord(c) > 126 for c in self.base_url):
            raise ValueError("Invalid ASR service URL")
        try:
            parts = urlsplit(self.base_url)
            host, port = parts.hostname, parts.port
            valid_url = (
                parts.scheme in {"https", "http"} and bool(host) and not parts.username and not parts.password
                and "@" not in parts.netloc and not parts.query and not parts.fragment
                and "\\" not in self.base_url and port != 0
            )
        except ValueError:
            valid_url = False
            parts = None
            host = None
        if not valid_url:
            raise ValueError("ASR service requires an absolute URL without credentials, query or fragment")
        if type(self.allow_local_http) is not bool:
            raise ValueError("Invalid local test setting")
        if parts.scheme != "https" and not (self.allow_local_http and host in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("ASR service URL must use HTTPS")
        for label in (self.provider, self.version):
            if not isinstance(label, str) or not label.strip() or len(label) > 100 or any(ord(c) < 32 for c in label):
                raise ValueError("Invalid ASR provider identity")
        if not isinstance(self.api_key, str) or not self.api_key or len(self.api_key) > 4096 \
                or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key):
            raise ValueError("A valid ASR API key is required")
        if type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds) \
                or not 0.1 <= self.timeout_seconds <= 300:
            raise ValueError("ASR timeout is outside the allowed range")
        for value, minimum, maximum in (
            (self.max_response_bytes, 1024, 64 * 1024 * 1024),
            (self.max_request_bytes, 1024, 64 * 1024 * 1024),
            (self.max_segment_bytes, 1, 64 * 1024 * 1024),
            (self.max_segment_ms, 1, 24 * 60 * 60 * 1000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("ASR resource limit is outside the allowed range")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonstandard JSON number")


class HttpAsrProvider:
    """Send one prepared audio segment to an explicitly injected JSON service."""

    def __init__(self, config: HttpAsrConfig):
        self.config = config
        handlers = [_NoRedirect()]
        if config.allow_local_http and urlsplit(config.base_url).hostname in {"127.0.0.1", "localhost", "::1"}:
            handlers.append(ProxyHandler({}))
        self._opener = build_opener(*handlers)

    def describe(self) -> AsrCapability:
        return AsrCapability(
            provider=self.config.provider, version=self.config.version, execution="external_service",
            media_types=["audio/wav", "audio/mpeg", "audio/mp4", "audio/flac", "audio/ogg"],
            max_segment_bytes=self.config.max_segment_bytes, max_segment_ms=self.config.max_segment_ms,
            word_timestamps=True, diarization=True,
        )

    def transcribe(self, request: AsrRequest) -> AsrResponse:
        body = self._request_body(request)
        http_request = Request(self.config.base_url.rstrip("/") + "/transcribe", data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.config.api_key}",
            "Idempotency-Key": request.idempotency_key,
        })
        try:
            with self._opener.open(http_request, timeout=min(request.timeout_seconds, self.config.timeout_seconds)) as response:
                if not 200 <= response.status < 300:
                    raise self._status_error(response.status)
                raw = self._read_response(response)
        except AsrProviderError:
            raise
        except HTTPError as error:
            try:
                failure = self._status_error(error.code)
            finally:
                error.close()
            raise failure from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise AsrProviderError("provider_timeout", "ASR service timed out; billing may be unknown", 504,
                                       retryable=True) from None
            raise AsrProviderError("provider_unavailable", "Could not reach ASR service", 503, retryable=True) from None
        except TimeoutError:
            raise AsrProviderError("provider_timeout", "ASR service timed out; billing may be unknown", 504,
                                   retryable=True) from None
        except (OSError, HTTPException):
            raise AsrProviderError("provider_unavailable", "ASR service connection failed", 503, retryable=True) from None
        try:
            decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            return self._map_response(decoded, request)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise AsrProviderError("provider_invalid_response", "ASR service returned an invalid response") from None

    def _request_body(self, request: AsrRequest) -> bytes:
        segment = request.segment
        if (segment.artifact.role != "derived" or segment.artifact.size_bytes != len(segment.content)
                or segment.artifact.sha256 != hashlib.sha256(segment.content).hexdigest()):
            raise AsrProviderError("provider_invalid_request", "Invalid prepared audio artifact", 422)
        if segment.artifact.media_type not in self.describe().media_types:
            raise AsrProviderError("provider_invalid_request", "Unsupported audio media type", 422)
        if len(segment.content) > self.config.max_segment_bytes or segment.end_ms - segment.start_ms > self.config.max_segment_ms:
            raise AsrProviderError("provider_request_limit", "Audio segment exceeds configured limits", 413)
        payload = {
            "audio_base64": base64.b64encode(segment.content).decode("ascii"),
            "media_type": segment.artifact.media_type,
            "start_ms": segment.start_ms, "end_ms": segment.end_ms,
            "language": request.language, "word_timestamps": request.word_timestamps,
            "diarization": request.diarization, "trace_id": request.trace_id,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > self.config.max_request_bytes:
            raise AsrProviderError("provider_request_limit", "ASR request exceeds configured limits", 413)
        return body

    def _map_response(self, decoded, request: AsrRequest) -> AsrResponse:
        if not isinstance(decoded, dict):
            raise ValueError("Expected ASR object")
        provider = decoded.get("provider", self.config.provider)
        model = decoded.get("model")
        if not isinstance(provider, str) or not provider or not isinstance(model, str) or not model:
            raise ValueError("Missing ASR provider/model")
        raw_segments = decoded.get("segments")
        if not isinstance(raw_segments, list) or len(raw_segments) > 10000:
            raise ValueError("Invalid ASR segments")
        offset = request.segment.start_ms
        segments = []
        for raw in raw_segments:
            if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
                raise ValueError("Invalid ASR segment")
            start = raw.get("start_ms")
            end = raw.get("end_ms")
            if type(start) is not int or type(end) is not int or start < 0 or end <= start:
                raise ValueError("Invalid ASR segment range")
            words = []
            for word in raw.get("words", []):
                if not isinstance(word, dict) or not isinstance(word.get("text"), str):
                    raise ValueError("Invalid ASR word")
                word_start, word_end = word.get("start_ms"), word.get("end_ms")
                if type(word_start) is not int or type(word_end) is not int or word_start < start or word_end > end:
                    raise ValueError("Invalid ASR word range")
                words.append(TranscriptWord(text=word["text"], start_ms=offset + word_start,
                                            end_ms=offset + word_end, speaker=word.get("speaker")))
            segments.append(TranscriptSegment(text=raw["text"], start_ms=offset + start, end_ms=offset + end,
                                              words=words, speaker=raw.get("speaker")))
        usage = decoded.get("usage", {})
        if not isinstance(usage, dict):
            raise ValueError("Invalid ASR usage")
        input_ms, cost = usage.get("input_ms"), usage.get("cost_micros")
        if input_ms is not None and (type(input_ms) is not int or input_ms < 0):
            raise ValueError("Invalid ASR input usage")
        if cost is not None and (type(cost) is not int or cost < 0):
            raise ValueError("Invalid ASR cost")
        return AsrResponse(provider=provider, model=model, source_id=request.segment.source_id,
                           stream_index=request.segment.stream_index, segment_start_ms=request.segment.start_ms,
                           segment_end_ms=request.segment.end_ms, language=decoded.get("language", request.language),
                           segments=segments, usage=AsrUsage(input_ms=input_ms, cost_micros=cost))

    def _read_response(self, response: HTTPResponse) -> bytes:
        if response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise AsrProviderError("provider_invalid_response", "Expected uncompressed JSON response")
        lengths = response.headers.get_all("Content-Length", [])
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise AsrProviderError("provider_invalid_response", "Invalid ASR response length")
            if int(lengths[0]) > self.config.max_response_bytes:
                raise AsrProviderError("provider_response_limit", "ASR response exceeds configured limit")
        raw = response.read(self.config.max_response_bytes + 1)
        if len(raw) > self.config.max_response_bytes:
            raise AsrProviderError("provider_response_limit", "ASR response exceeds configured limit")
        return raw

    @staticmethod
    def _status_error(status: int) -> AsrProviderError:
        if 300 <= status < 400:
            return AsrProviderError("provider_redirect", "ASR service redirects are not allowed")
        code = {401: "provider_auth_failed", 403: "provider_auth_failed", 402: "provider_billing_required",
                404: "provider_not_found", 408: "provider_timeout", 429: "provider_rate_limited"}.get(status)
        if code:
            return AsrProviderError(code, "ASR service rejected the request", retryable=status in {408, 429})
        if status >= 500:
            return AsrProviderError("provider_unavailable", "ASR service is temporarily unavailable", 503, retryable=True)
        return AsrProviderError("provider_invalid_request", "ASR service rejected the request")
