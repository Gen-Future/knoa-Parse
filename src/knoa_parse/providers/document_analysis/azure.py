"""Azure AI Document Intelligence adapter for the internal page-analysis port.

This module intentionally has no Azure SDK dependency.  It uses the service's
HTTPS REST API, submits one already-prepared page image, polls the returned
operation, and converts only text lines with pixel polygons into the current
``PageAnalysis`` contract.  Tables, figures, and other fields are rejected
until a richer document-understanding result contract exists; silently
discarding them would make a successful response misleading.
"""
import base64
import hashlib
import json
import math
import re
import time
from dataclasses import dataclass, field
from http.client import HTTPException, HTTPResponse
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from knoa_parse.core.document_analysis import (
    DocumentCapability,
    PageAnalysis,
    PageRequest,
    RecognizedElement,
)
from .http import DocumentProviderError


class AzureDocumentProviderError(DocumentProviderError):
    """Safe adapter error with the remote operation retained for recovery."""

    def __init__(self, code: str, message: str, status_code: int = 502, *,
                 retryable: bool = False, operation: "AzureOperation | None" = None):
        super().__init__(code, message, status_code, retryable=retryable)
        self.operation = operation


@dataclass(frozen=True)
class AzureDocumentAnalysisConfig:
    """Configuration for one Azure Document Intelligence resource."""

    endpoint: str
    api_key: str = field(repr=False)
    model_id: str = "prebuilt-layout"
    api_version: str = "2024-11-30"
    locale: str | None = None
    timeout_seconds: float = 60.0
    poll_interval_seconds: float = 0.5
    max_poll_interval_seconds: float = 10.0
    max_response_bytes: int = 16 * 1024 * 1024
    max_request_bytes: int = 16 * 1024 * 1024
    max_page_bytes: int = 10 * 1024 * 1024
    max_pixels: int = 40_000_000
    allow_local_http: bool = False

    def __post_init__(self):
        if not isinstance(self.endpoint, str) or any(ord(c) < 33 or ord(c) > 126 for c in self.endpoint):
            raise ValueError("Invalid Azure endpoint")
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
            raise ValueError("Azure endpoint requires an absolute URL without credentials, query or fragment")
        if parts.scheme != "https" and not (self.allow_local_http and host in {"127.0.0.1", "localhost", "::1"}):
            raise ValueError("Azure endpoint must use HTTPS")
        if type(self.allow_local_http) is not bool:
            raise ValueError("Invalid local test setting")
        if not isinstance(self.api_key, str) or not self.api_key or len(self.api_key) > 4096 \
                or any(ord(c) < 33 or ord(c) > 126 for c in self.api_key):
            raise ValueError("A valid Azure API key is required")
        if not isinstance(self.model_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", self.model_id):
            raise ValueError("Invalid Azure model ID")
        if not isinstance(self.api_version, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.api_version):
            raise ValueError("Invalid Azure API version")
        if self.locale is not None and (
            not isinstance(self.locale, str) or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z]{2,4})?", self.locale)
        ):
            raise ValueError("Invalid Azure locale")
        for value, minimum, maximum in (
            (self.timeout_seconds, 0.1, 300.0),
            (self.poll_interval_seconds, 0.01, 30.0),
            (self.max_poll_interval_seconds, 0.01, 60.0),
        ):
            if type(value) not in {int, float} or not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError("Azure polling setting is outside the allowed range")
        if self.max_poll_interval_seconds < self.poll_interval_seconds:
            raise ValueError("Maximum Azure poll interval cannot be shorter than the base interval")
        for value, minimum, maximum in (
            (self.max_response_bytes, 1024, 64 * 1024 * 1024),
            (self.max_request_bytes, 1024, 64 * 1024 * 1024),
            (self.max_page_bytes, 1, 20 * 1024 * 1024),
            (self.max_pixels, 1, 100_000_000),
        ):
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError("Azure resource limit is outside the allowed range")


@dataclass(frozen=True)
class AzureOperation:
    """Remote operation reference returned by Azure after submission."""

    operation_location: str
    remote_job_id: str


@dataclass(frozen=True)
class AzureAnalysisResult:
    """Mapped page plus operation metadata; raw data stays in memory by default."""

    operation: AzureOperation
    analysis: PageAnalysis
    raw_response: dict = field(repr=False)


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


def _finite_number(value) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


class AzureDocumentAnalysisProvider:
    """Submit one prepared page image to Azure Document Intelligence."""

    def __init__(self, config: AzureDocumentAnalysisConfig):
        self.config = config
        handlers = [_NoRedirect()]
        if config.allow_local_http and urlsplit(config.endpoint).hostname in {"127.0.0.1", "localhost", "::1"}:
            handlers.append(ProxyHandler({}))
        self._opener = build_opener(*handlers)

    def describe(self) -> DocumentCapability:
        return DocumentCapability(
            provider="azure-document-intelligence",
            version=self.config.api_version,
            execution="external_service",
            media_types=["image/png", "image/jpeg"],
            max_page_bytes=self.config.max_page_bytes,
            max_pixels=self.config.max_pixels,
            coordinate_units=["px"],
        )

    def _analyze_url(self) -> str:
        base = self.config.endpoint.rstrip("/")
        return f"{base}/documentintelligence/documentModels/{self.config.model_id}:analyze?" + urlencode({
            "api-version": self.config.api_version,
        })

    def _request_body(self, request: PageRequest) -> bytes:
        page = request.page
        if (page.artifact.media_type not in {"image/png", "image/jpeg"}
                or page.artifact.role != "derived" or page.artifact.size_bytes != len(page.content)
                or page.artifact.sha256 != hashlib.sha256(page.content).hexdigest()):
            raise AzureDocumentProviderError("provider_invalid_request", "Invalid prepared page artifact", 422)
        if len(page.content) > self.config.max_page_bytes or page.width_px * page.height_px > self.config.max_pixels:
            raise AzureDocumentProviderError("provider_request_limit", "Document request exceeds configured limits", 413)
        payload = {"base64Source": base64.b64encode(page.content).decode("ascii")}
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("ascii")
        if len(body) > self.config.max_request_bytes:
            raise AzureDocumentProviderError("provider_request_limit", "Document request exceeds configured limits", 413)
        return body

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "Ocp-Apim-Subscription-Key": self.config.api_key,
        }

    def submit_page(self, request: PageRequest) -> AzureOperation:
        try:
            body = self._request_body(request)
        except AzureDocumentProviderError:
            raise
        except (ValueError, TypeError, OverflowError):
            raise AzureDocumentProviderError("provider_invalid_request", "Invalid document analysis request", 422) from None
        http_request = Request(self._analyze_url(), data=body, method="POST", headers=self._headers())
        try:
            with self._opener.open(http_request, timeout=min(request.timeout_seconds, self.config.timeout_seconds)) as response:
                if response.status != 202:
                    raise self._status_error(response.status)
                operation_location = response.headers.get("Operation-Location")
                self._discard_response(response)
        except AzureDocumentProviderError:
            raise
        except HTTPError as error:
            try:
                failure = self._status_error(error.code)
            finally:
                error.close()
            raise failure from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise AzureDocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504,
                                                 retryable=False) from None
            raise AzureDocumentProviderError("provider_unavailable", "Could not reach document service", 503,
                                             retryable=True) from None
        except TimeoutError:
            raise AzureDocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504,
                                             retryable=False) from None
        except (OSError, HTTPException):
            raise AzureDocumentProviderError("provider_unavailable", "Document service connection failed", 503,
                                             retryable=True) from None
        try:
            operation = self._validate_operation_location(operation_location)
        except (TypeError, ValueError):
            raise AzureDocumentProviderError("provider_invalid_response", "Document service returned an invalid operation location") from None
        return operation

    def poll_page(self, operation: AzureOperation, request: PageRequest) -> AzureAnalysisResult:
        timeout = min(request.timeout_seconds, self.config.timeout_seconds)
        deadline = time.monotonic() + timeout
        delay = self.config.poll_interval_seconds
        while True:
            payload, retry_after = self._get_operation(operation, request)
            status = payload.get("status")
            if not isinstance(status, str):
                raise AzureDocumentProviderError("provider_invalid_response", "Document service returned an invalid operation status",
                                                 operation=operation)
            status = status.lower()
            if status == "succeeded":
                try:
                    analysis = self._map_result(payload, request)
                except (TypeError, ValueError, KeyError, OverflowError, RecursionError):
                    raise AzureDocumentProviderError("provider_invalid_response", "Document service returned an invalid analysis result",
                                                     operation=operation) from None
                return AzureAnalysisResult(operation=operation, analysis=analysis, raw_response=payload)
            if status in {"failed", "cancelled", "canceled"}:
                code = "provider_remote_cancelled" if status in {"cancelled", "canceled"} else "provider_remote_failed"
                raise AzureDocumentProviderError(code, "Document service did not complete the operation", operation=operation)
            if status not in {"notstarted", "running"}:
                raise AzureDocumentProviderError("provider_invalid_response", "Document service returned an unknown operation status",
                                                 operation=operation)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AzureDocumentProviderError("provider_timeout", "Document service operation timed out; billing may be unknown",
                                                 504, retryable=False, operation=operation)
            if retry_after is not None:
                delay = min(self.config.max_poll_interval_seconds, max(self.config.poll_interval_seconds, retry_after))
            delay = min(delay, remaining)
            time.sleep(delay)
            delay = min(self.config.max_poll_interval_seconds, max(self.config.poll_interval_seconds, delay * 2))

    def analyze_page(self, request: PageRequest) -> PageAnalysis:
        operation = self.submit_page(request)
        return self.poll_page(operation, request).analysis

    def _get_operation(self, operation: AzureOperation, request: PageRequest) -> tuple[dict, float | None]:
        http_request = Request(operation.operation_location, method="GET", headers=self._headers())
        try:
            with self._opener.open(http_request, timeout=min(request.timeout_seconds, self.config.timeout_seconds)) as response:
                if response.status != 200:
                    raise self._status_error(response.status)
                retry_after = self._retry_after(response.headers.get("Retry-After"))
                raw = self._read_json_response(response)
        except AzureDocumentProviderError as error:
            if error.operation is None:
                error.operation = operation
            raise
        except HTTPError as error:
            try:
                failure = self._status_error(error.code)
            finally:
                error.close()
            failure.operation = operation
            raise failure from None
        except URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise AzureDocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504,
                                                 retryable=False, operation=operation) from None
            raise AzureDocumentProviderError("provider_unavailable", "Could not reach document service", 503,
                                             retryable=True, operation=operation) from None
        except TimeoutError:
            raise AzureDocumentProviderError("provider_timeout", "Document service timed out; billing may be unknown", 504,
                                             retryable=False, operation=operation) from None
        except (OSError, HTTPException):
            raise AzureDocumentProviderError("provider_unavailable", "Document service connection failed", 503,
                                             retryable=True, operation=operation) from None
        try:
            decoded = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            if not isinstance(decoded, dict):
                raise ValueError("Expected object")
            return decoded, retry_after
        except (UnicodeDecodeError, ValueError, TypeError, RecursionError):
            raise AzureDocumentProviderError("provider_invalid_response", "Document service returned invalid JSON",
                                             operation=operation) from None

    def _map_result(self, payload: dict, request: PageRequest) -> PageAnalysis:
        result = payload.get("analyzeResult")
        if not isinstance(result, dict):
            raise ValueError("Missing analyzeResult")
        pages = result.get("pages")
        if not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict):
            raise ValueError("Expected one page result")
        page = pages[0]
        page_number = page.get("pageNumber", 1)
        if page_number != 1:
            raise ValueError("Unexpected service page number")
        unit = page.get("unit")
        width, height = page.get("width"), page.get("height")
        if unit != "pixel" or not _finite_number(width) or not _finite_number(height) or width <= 0 or height <= 0:
            raise ValueError("Expected pixel page dimensions")
        if abs((width / height) - (request.page.width_px / request.page.height_px)) > 0.02 * max(width / height, 1):
            raise ValueError("Service page dimensions do not match the prepared page")
        if result.get("tables") or result.get("figures") or page.get("tables") or page.get("figures"):
            raise ValueError("Structured service output requires the document-understanding contract")
        lines = page.get("lines", [])
        if not isinstance(lines, list):
            raise ValueError("Invalid lines")
        elements = []
        for line in lines:
            if not isinstance(line, dict) or not isinstance(line.get("content"), str) or not line["content"].strip():
                raise ValueError("Invalid line")
            polygon = line.get("polygon")
            if not isinstance(polygon, list) or len(polygon) < 4 or len(polygon) % 2:
                raise ValueError("Line polygon is required")
            if not all(_finite_number(value) for value in polygon):
                raise ValueError("Invalid line polygon")
            xs, ys = polygon[0::2], polygon[1::2]
            bbox = [min(xs), min(ys), max(xs), max(ys)]
            if bbox[0] < 0 or bbox[1] < 0 or bbox[2] > width or bbox[3] > height or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                raise ValueError("Line polygon is outside page bounds")
            elements.append(RecognizedElement(text=line["content"], bbox=bbox, unit="px", origin="top_left"))
        return PageAnalysis(page=request.page.page, elements=elements, blank=not elements,
                            model=f"{self.config.model_id}@{self.config.api_version}")

    def _validate_operation_location(self, value: str | None) -> AzureOperation:
        if not isinstance(value, str) or any(ord(c) < 33 or ord(c) > 126 for c in value):
            raise ValueError("Missing operation location")
        location = urlsplit(value)
        base = urlsplit(self.config.endpoint)
        def effective_port(parts):
            if parts.port is not None:
                return parts.port
            return 443 if parts.scheme == "https" else 80
        if (location.scheme != base.scheme or location.hostname != base.hostname
                or effective_port(location) != effective_port(base) or not location.path
                or location.username or location.password or location.fragment):
            raise ValueError("Operation location is outside the configured resource")
        remote_job_id = location.path.rstrip("/").rsplit("/", 1)[-1]
        if not remote_job_id or len(remote_job_id) > 200:
            raise ValueError("Missing remote job ID")
        return AzureOperation(operation_location=value, remote_job_id=remote_job_id)

    def _read_json_response(self, response: HTTPResponse) -> bytes:
        if response.headers.get_content_type() != "application/json" or response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise AzureDocumentProviderError("provider_invalid_response", "Expected uncompressed JSON response")
        return self._read_response(response)

    def _read_response(self, response: HTTPResponse) -> bytes:
        lengths = response.headers.get_all("Content-Length", [])
        length = None
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                raise AzureDocumentProviderError("provider_invalid_response", "Invalid document response length")
            length = int(lengths[0])
            if length > self.config.max_response_bytes:
                raise AzureDocumentProviderError("provider_response_limit", "Document response exceeds configured limit")
        data = response.read(self.config.max_response_bytes + 1)
        if len(data) > self.config.max_response_bytes:
            raise AzureDocumentProviderError("provider_response_limit", "Document response exceeds configured limit")
        if length is not None and len(data) != length:
            raise AzureDocumentProviderError("provider_invalid_response", "Document response is truncated")
        return data

    def _discard_response(self, response: HTTPResponse):
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise AzureDocumentProviderError("provider_invalid_response", "Compressed service response is not allowed")
        response.read(min(self.config.max_response_bytes, 1024))

    @staticmethod
    def _retry_after(value: str | None) -> float | None:
        if value is None or not value.isascii() or not value.strip().isdigit():
            return None
        return float(value.strip())

    @staticmethod
    def _status_error(status: int) -> AzureDocumentProviderError:
        if 300 <= status < 400:
            return AzureDocumentProviderError("provider_redirect", "Document service redirects are not allowed")
        code = {
            401: "provider_auth_failed", 403: "provider_auth_failed", 402: "provider_billing_required",
            404: "provider_not_found", 408: "provider_timeout", 409: "provider_conflict",
            429: "provider_rate_limited",
        }.get(status)
        if code:
            return AzureDocumentProviderError(code, "Document service rejected the request", retryable=status in {408, 429})
        if status >= 500:
            return AzureDocumentProviderError("provider_unavailable", "Document service is temporarily unavailable", 503,
                                             retryable=True)
        return AzureDocumentProviderError("provider_invalid_request", "Document service rejected the request")
