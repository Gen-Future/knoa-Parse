"""Opt-in adapter for Knoa's internal page JSON protocol, not a vendor OCR API."""
import base64
import hashlib
import json
import math
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from knoa_parse.core.document_analysis import DocumentCapability, PageAnalysis, PageRequest
from knoa_parse.core.errors import ProviderError


class DocumentProviderError(ProviderError):
    """Stable, sanitized error; shares the orchestration provider-error contract."""


@dataclass(frozen=True)
class HttpDocumentAnalysisConfig:
    provider: str
    base_url: str
    api_key: str = field(repr=False)
    version: str = "http-json-v1"
    timeout_seconds: float = 60.0
    max_response_bytes: int = 4 * 1024 * 1024
    max_request_bytes: int = 16 * 1024 * 1024
    max_page_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 40_000_000
    allow_local_http: bool = False

    def __post_init__(self):
        if not isinstance(self.base_url, str) or any(ord(c) < 33 or ord(c) > 126 for c in self.base_url):
            raise ValueError("Invalid document service URL")
        try:
            parts = urlsplit(self.base_url)
            host, port = parts.hostname, parts.port
            valid_url = (
                parts.scheme in {"https", "http"} and bool(host) and not parts.username and not parts.password
                and "@" not in parts.netloc and "?" not in self.base_url and "#" not in self.base_url
                and "\\" not in self.base_url and port != 0
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            raise ValueError("Document service requires an absolute URL without credentials, query or fragment")
        if type(self.allow_local_http) is not bool:
            raise ValueError("Invalid local test setting")
        if parts.scheme != "https" and not (self.allow_local_http and host in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("Document service URL must use HTTPS")
        for label in (self.provider, self.version):
            if not isinstance(label, str) or not label.strip() or len(label) > 100 or any(ord(c) < 32 for c in label):
                raise ValueError("Invalid document provider identity")
        if (not isinstance(self.api_key, str) or not self.api_key or len(self.api_key) > 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key)):
            raise ValueError("A valid document service API key is required")
        if (type(self.timeout_seconds) not in {int, float} or not math.isfinite(self.timeout_seconds)
                or not 0.1 <= self.timeout_seconds <= 300):
            raise ValueError("Document service timeout is outside the allowed range")
        for value, minimum, maximum in (
            (self.max_response_bytes, 1024, 64 * 1024 * 1024),
            (self.max_request_bytes, 1024, 64 * 1024 * 1024),
            (self.max_page_bytes, 1, 20 * 1024 * 1024),
            (self.max_pixels, 1, 100_000_000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Document service resource limit is outside the allowed range")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Returning None lets urllib raise HTTPError, which is closed by the caller.
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


class HttpDocumentAnalysisProvider:
    """Send exactly one prepared page to an explicitly injected JSON endpoint."""

    def __init__(self, config: HttpDocumentAnalysisConfig):
        self.config = config
        handlers = [_NoRedirect()]
        if config.allow_local_http and urlsplit(config.base_url).hostname in {"127.0.0.1", "localhost", "::1"}:
            handlers.append(ProxyHandler({}))
        self._opener = build_opener(*handlers)

    def describe(self) -> DocumentCapability:
        return DocumentCapability(
            provider=self.config.provider, version=self.config.version,
            execution="external_service", media_types=["image/png", "image/jpeg"],
            max_page_bytes=self.config.max_page_bytes, max_pixels=self.config.max_pixels,
            coordinate_units=["px", "normalized"],
        )

    def _request_body(self, request: PageRequest) -> bytes:
        page = request.page
        if (page.artifact.media_type not in {"image/png", "image/jpeg"}
                or page.artifact.role != "derived" or page.artifact.size_bytes != len(page.content)
                or page.artifact.sha256 != hashlib.sha256(page.content).hexdigest()):
            raise DocumentProviderError("provider_invalid_request", "Invalid prepared page artifact", 422)
        if (len(page.content) > self.config.max_page_bytes
                or page.width_px * page.height_px > self.config.max_pixels
                or sum(len(item.text) for item in request.context) > self.config.max_request_bytes):
            raise DocumentProviderError("provider_request_limit", "Document request exceeds configured limits", 413)
        payload = {
            "page": page.page, "media_type": page.artifact.media_type,
            "width_px": page.width_px, "height_px": page.height_px,
            "width_pt": page.width_pt, "height_pt": page.height_pt,
            "image_base64": base64.b64encode(page.content).decode("ascii"),
            "context": [item.model_dump() for item in request.context], "trace_id": request.trace_id,
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > self.config.max_request_bytes:
            raise DocumentProviderError("provider_request_limit", "Document request exceeds configured limits", 413)
        return body

    def analyze_page(self, request: PageRequest) -> PageAnalysis:
        try:
            request = PageRequest.model_validate(request.model_dump(exclude={"page"}) | {
                "page": request.page.model_dump() | {"content": request.page.content},
            })
            body = self._request_body(request)
        except (ValueError, TypeError, OverflowError):
            raise DocumentProviderError("provider_invalid_request", "Invalid document analysis request", 422) from None
        http_request = Request(self.config.base_url.rstrip("/") + "/analyze/page", data=body, method="POST", headers={
            "Accept": "application/json", "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.config.api_key}",
        })
        try:
            with self._opener.open(http_request, timeout=min(request.timeout_seconds, self.config.timeout_seconds)) as response:
                if not 200 <= response.status < 300:
                    raise self._status_error(response.status)
                raw = self._read_response(response)
        except DocumentProviderError:
            raise
        except HTTPError as error:
            try:
                failure = self._status_error(error.code)
            finally:
                error.close()
            raise failure from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise DocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504, retryable=True) from None
            raise DocumentProviderError("provider_unavailable", "Could not reach document service", 503, retryable=True) from None
        except TimeoutError:
            raise DocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504, retryable=True) from None
        except (OSError, HTTPException):
            raise DocumentProviderError("provider_unavailable", "Document service connection failed", 503, retryable=True) from None
        try:
            decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            result = PageAnalysis.model_validate(decoded)
            if result.page != request.page.page:
                raise ValueError("Wrong response page")
            return result
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            raise DocumentProviderError("provider_invalid_response", "Document service returned an invalid response") from None

    def _read_response(self, response: HTTPResponse) -> bytes:
        if response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise DocumentProviderError("provider_invalid_response", "Expected uncompressed JSON response")
        lengths = response.headers.get_all("Content-Length", [])
        length = None
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise DocumentProviderError("provider_invalid_response", "Invalid document response length")
            length = int(lengths[0])
            if length > self.config.max_response_bytes:
                raise DocumentProviderError("provider_response_limit", "Document response exceeds configured limit")
        data = response.read(self.config.max_response_bytes + 1)
        if len(data) > self.config.max_response_bytes:
            raise DocumentProviderError("provider_response_limit", "Document response exceeds configured limit")
        if length is not None and len(data) != length:
            raise DocumentProviderError("provider_invalid_response", "Document response is truncated")
        return data

    @staticmethod
    def _status_error(status: int) -> DocumentProviderError:
        if 300 <= status < 400:
            return DocumentProviderError("provider_redirect", "Document service redirects are not allowed")
        code = {401: "provider_auth_failed", 403: "provider_auth_failed", 402: "provider_billing_required",
                404: "provider_not_found", 408: "provider_timeout", 429: "provider_rate_limited"}.get(status)
        if code:
            return DocumentProviderError(code, "Document service rejected the request", retryable=status in {408, 429})
        if status >= 500:
            return DocumentProviderError("provider_unavailable", "Document service is temporarily unavailable", 503, retryable=True)
        return DocumentProviderError("provider_invalid_request", "Document service rejected the request")
