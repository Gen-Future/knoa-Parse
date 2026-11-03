"""Azure Speech fast-transcription adapter (REST API 2025-10-15).

The adapter uses the public multipart REST surface and maps phrase/word
offsets back into Knoa's source timeline.  It has no Azure SDK or local ASR
dependency and is not registered in a product route until live acceptance.
"""
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from knoa_parse.core.asr import AsrCapability, AsrRequest, AsrResponse, AsrUsage, TranscriptSegment, TranscriptWord
from knoa_parse.core.errors import ProviderError


class AzureSpeechError(ProviderError):
    """Stable, sanitized Azure Speech adapter error."""


@dataclass(frozen=True)
class AzureSpeechConfig:
    endpoint: str
    api_key: str = field(repr=False)
    api_version: str = "2025-10-15"
    timeout_seconds: float = 60.0
    max_response_bytes: int = 16 * 1024 * 1024
    max_request_bytes: int = 64 * 1024 * 1024
    max_segment_bytes: int = 250 * 1024 * 1024
    max_segment_ms: int = 2 * 60 * 60 * 1000
    allow_local_http: bool = False

    def __post_init__(self):
        if not isinstance(self.endpoint, str) or any(ord(c) < 33 or ord(c) > 126 for c in self.endpoint):
            raise ValueError("Invalid Azure Speech endpoint")
        try:
            parts = urlsplit(self.endpoint)
            host, port = parts.hostname, parts.port
            valid_url = (
                parts.scheme in {"https", "http"} and bool(host) and not parts.username and not parts.password
                and "@" not in parts.netloc and not parts.query and not parts.fragment
                and "\\" not in self.endpoint and port != 0
            )
        except ValueError:
            valid_url = False
            parts = None
            host = None
        if not valid_url:
            raise ValueError("Azure Speech endpoint requires an absolute URL without credentials, query or fragment")
        if type(self.allow_local_http) is not bool:
            raise ValueError("Invalid local test setting")
        if parts.scheme != "https" and not (self.allow_local_http and host in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("Azure Speech endpoint must use HTTPS")
        if self.api_version != "2025-10-15":
            raise ValueError("Only the audited Azure Speech API version is enabled")
        if not isinstance(self.api_key, str) or not self.api_key or len(self.api_key) > 4096 \
                or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key):
            raise ValueError("A valid Azure Speech API key is required")
        if type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds) \
                or not 0.1 <= self.timeout_seconds <= 300:
            raise ValueError("Azure Speech timeout is outside the allowed range")
        for value, minimum, maximum in (
            (self.max_response_bytes, 1024, 64 * 1024 * 1024),
            (self.max_request_bytes, 1024, 300 * 1024 * 1024),
            (self.max_segment_bytes, 1, 250 * 1024 * 1024),
            (self.max_segment_ms, 1, 2 * 60 * 60 * 1000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Azure Speech resource limit is outside the allowed range")


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


class AzureSpeechFastTranscriptionProvider:
    """Map Azure's synchronous fast transcription response to AsrResponse."""

    _MEDIA_EXTENSIONS = {"audio/wav": "wav", "audio/mpeg": "mp3", "audio/mp4": "m4a",
                         "audio/flac": "flac", "audio/ogg": "ogg"}

    def __init__(self, config: AzureSpeechConfig):
        self.config = config
        handlers = [_NoRedirect()]
        if config.allow_local_http and urlsplit(config.endpoint).hostname in {"127.0.0.1", "localhost", "::1"}:
            handlers.append(ProxyHandler({}))
        self._opener = build_opener(*handlers)

    def describe(self) -> AsrCapability:
        return AsrCapability(provider="azure-speech", version=self.config.api_version, execution="external_service",
                             media_types=list(self._MEDIA_EXTENSIONS), max_segment_bytes=self.config.max_segment_bytes,
                             max_segment_ms=self.config.max_segment_ms, word_timestamps=True, diarization=True)

    def transcribe(self, request: AsrRequest) -> AsrResponse:
        body, content_type = self._multipart_body(request)
        url = self.config.endpoint.rstrip("/") + "/speechtotext/transcriptions:transcribe?" + urlencode({
            "api-version": self.config.api_version,
        })
        http_request = Request(url, data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": content_type,
            "Ocp-Apim-Subscription-Key": self.config.api_key,
        })
        try:
            with self._opener.open(http_request, timeout=min(request.timeout_seconds, self.config.timeout_seconds)) as response:
                if response.status != 200:
                    raise self._status_error(response.status)
                raw = self._read_response(response)
        except AzureSpeechError:
            raise
        except HTTPError as error:
            try:
                failure = self._status_error(error.code)
            finally:
                error.close()
            raise failure from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise AzureSpeechError("provider_timeout", "Azure Speech timed out; billing may be unknown", 504,
                                       retryable=True) from None
            raise AzureSpeechError("provider_unavailable", "Could not reach Azure Speech", 503, retryable=True) from None
        except TimeoutError:
            raise AzureSpeechError("provider_timeout", "Azure Speech timed out; billing may be unknown", 504,
                                   retryable=True) from None
        except (OSError, HTTPException):
            raise AzureSpeechError("provider_unavailable", "Azure Speech connection failed", 503, retryable=True) from None
        try:
            decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            return self._map_response(decoded, request)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
            raise AzureSpeechError("provider_invalid_response", "Azure Speech returned an invalid response") from None

    def _multipart_body(self, request: AsrRequest) -> tuple[bytes, str]:
        segment = request.segment
        if (segment.artifact.role != "derived" or segment.artifact.size_bytes != len(segment.content)
                or segment.artifact.sha256 != hashlib.sha256(segment.content).hexdigest()):
            raise AzureSpeechError("provider_invalid_request", "Invalid prepared audio artifact", 422)
        media_type = segment.artifact.media_type
        if media_type not in self._MEDIA_EXTENSIONS:
            raise AzureSpeechError("provider_invalid_request", "Unsupported Azure Speech audio media type", 422)
        duration = segment.end_ms - segment.start_ms
        if len(segment.content) > self.config.max_segment_bytes or duration > self.config.max_segment_ms:
            raise AzureSpeechError("provider_request_limit", "Azure Speech segment exceeds configured limits", 413)
        definition = {"wordLevelTimestampsEnabled": request.word_timestamps}
        if request.language:
            definition["locales"] = [request.language]
        if request.diarization:
            definition["diarization"] = {"enabled": True}
        boundary = "----knoa-" + uuid.uuid4().hex
        lines = []
        lines.extend([f"--{boundary}\r\n".encode(),
                      b'Content-Disposition: form-data; name="definition"\r\n',
                      b"Content-Type: application/json\r\n\r\n",
                      json.dumps(definition, separators=(",", ":"), ensure_ascii=True).encode("ascii"), b"\r\n"])
        lines.extend([f"--{boundary}\r\n".encode(),
                      f'Content-Disposition: form-data; name="audio"; filename="segment.{self._MEDIA_EXTENSIONS[media_type]}"\r\n'.encode(),
                      f"Content-Type: {media_type}\r\n\r\n".encode(), segment.content, b"\r\n",
                      f"--{boundary}--\r\n".encode()])
        body = b"".join(lines)
        if len(body) > self.config.max_request_bytes:
            raise AzureSpeechError("provider_request_limit", "Azure Speech request exceeds configured limits", 413)
        return body, f"multipart/form-data; boundary={boundary}"

    def _map_response(self, decoded, request: AsrRequest) -> AsrResponse:
        if not isinstance(decoded, dict) or not isinstance(decoded.get("phrases"), list):
            raise ValueError("Missing Azure Speech phrases")
        offset = request.segment.start_ms
        mapped = []
        for phrase in decoded["phrases"]:
            if not isinstance(phrase, dict) or not isinstance(phrase.get("text"), str):
                raise ValueError("Invalid Azure Speech phrase")
            start = phrase.get("offsetMilliseconds")
            duration = phrase.get("durationMilliseconds")
            if type(start) is not int or type(duration) is not int or start < 0 or duration <= 0:
                raise ValueError("Invalid Azure Speech phrase range")
            end = start + duration
            speaker = phrase.get("speaker")
            if speaker is not None and type(speaker) not in {int, str}:
                raise ValueError("Invalid Azure Speech speaker")
            words = []
            for word in phrase.get("words", []):
                if not isinstance(word, dict) or not isinstance(word.get("text"), str):
                    raise ValueError("Invalid Azure Speech word")
                word_start = word.get("offsetMilliseconds")
                word_duration = word.get("durationMilliseconds")
                if type(word_start) is not int or type(word_duration) is not int or word_start < start \
                        or word_duration <= 0 or word_start + word_duration > end:
                    raise ValueError("Invalid Azure Speech word range")
                words.append(TranscriptWord(text=word["text"], start_ms=offset + word_start,
                                            end_ms=offset + word_start + word_duration,
                                            speaker=str(speaker) if speaker is not None else None))
            mapped.append(TranscriptSegment(text=phrase["text"], start_ms=offset + start, end_ms=offset + end,
                                            words=words, speaker=str(speaker) if speaker is not None else None))
        input_ms = decoded.get("durationMilliseconds")
        if input_ms is not None and (type(input_ms) is not int or input_ms < 0):
            raise ValueError("Invalid Azure Speech duration")
        language = decoded.get("locale")
        if language is None:
            language = next((phrase.get("locale") for phrase in decoded["phrases"]
                             if isinstance(phrase, dict) and isinstance(phrase.get("locale"), str)), None)
        return AsrResponse(provider="azure-speech", model="azure-transcribe", source_id=request.segment.source_id,
                           stream_index=request.segment.stream_index, segment_start_ms=request.segment.start_ms,
                           segment_end_ms=request.segment.end_ms, language=language or request.language,
                           segments=mapped, usage=AsrUsage(input_ms=input_ms, cost_micros=None))

    def _read_response(self, response: HTTPResponse) -> bytes:
        if response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise AzureSpeechError("provider_invalid_response", "Expected uncompressed JSON response")
        lengths = response.headers.get_all("Content-Length", [])
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise AzureSpeechError("provider_invalid_response", "Invalid Azure Speech response length")
            if int(lengths[0]) > self.config.max_response_bytes:
                raise AzureSpeechError("provider_response_limit", "Azure Speech response exceeds configured limit")
        raw = response.read(self.config.max_response_bytes + 1)
        if len(raw) > self.config.max_response_bytes:
            raise AzureSpeechError("provider_response_limit", "Azure Speech response exceeds configured limit")
        return raw

    @staticmethod
    def _status_error(status: int) -> AzureSpeechError:
        if 300 <= status < 400:
            return AzureSpeechError("provider_redirect", "Azure Speech redirects are not allowed")
        code = {401: "provider_auth_failed", 403: "provider_auth_failed", 404: "provider_not_found",
                408: "provider_timeout", 429: "provider_rate_limited"}.get(status)
        if code:
            return AzureSpeechError(code, "Azure Speech rejected the request", retryable=status in {408, 429})
        if status >= 500:
            return AzureSpeechError("provider_unavailable", "Azure Speech is temporarily unavailable", 503, retryable=True)
        return AzureSpeechError("provider_invalid_request", "Azure Speech rejected the request")
