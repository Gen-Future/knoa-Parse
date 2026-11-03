import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from knoa_parse.apps.model_services import text_provider_from_env
from knoa_parse.apps.configuration import server_configuration
from knoa_parse.providers.text_model.anthropic_compatible import AnthropicCompatibleTextProvider
from knoa_parse.core.text_model import ProviderError, TextRequest
from knoa_parse.providers.text_model.openai_compatible import (
    NoRedirect, OpenAICompatibleTextProvider, TextModelConfig,
)


def make_provider(**options):
    return OpenAICompatibleTextProvider(TextModelConfig(**{
        "provider": "siliconflow", "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "private-test-key", "model": "deepseek-ai/DeepSeek-V3.2", **options,
    }))


def install_response(provider, body=None, headers=None):
    if body is None:
        body = {"id": "completion-test", "model": provider.config.model,
                "choices": [{"message": {"content": "中文 OK"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15}}
    response = io.BytesIO(json.dumps(body).encode() if not isinstance(body, bytes) else body)
    response.headers = headers or {}
    provider.opener = Mock()
    provider.opener.open.return_value = response


class ModelServicesTests(unittest.TestCase):
    def test_anthropic_protocol_payload_content_and_usage(self):
        provider = AnthropicCompatibleTextProvider(TextModelConfig(
            provider="my-platform", protocol="anthropic", base_url="https://example.com/v1",
            model="configured-model", api_key="private-test-key"))
        install_response(provider, {"id": "msg-test", "model": "actual-model", "stop_reason": "end_turn",
                                   "content": [{"type": "thinking", "thinking": "hidden"},
                                               {"type": "text", "text": "中文"}, {"type": "text", "text": "OK"}],
                                   "usage": {"input_tokens": 10, "output_tokens": 2,
                                             "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}},
                         {"request-id": "trace-anthropic"})
        result = provider.complete(TextRequest(prompt="资料", system="System rule", max_tokens=64))
        req = provider.opener.open.call_args.args[0]
        wire = json.loads(req.data)
        self.assertEqual(req.full_url, "https://example.com/v1/messages")
        self.assertEqual(req.get_header("X-api-key"), "private-test-key")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
        self.assertIsNone(req.get_header("Authorization"))
        self.assertEqual(wire["system"], "System rule")
        self.assertEqual(wire["messages"], [{"role": "user", "content": "资料"}])
        self.assertNotIn("enable_thinking", wire)
        self.assertEqual(result.text, "中文OK")
        self.assertEqual(result.usage.prompt_tokens, 17)
        self.assertEqual(result.usage.total_tokens, 19)
        self.assertEqual(result.request_id, "trace-anthropic")
        self.assertEqual(provider.describe()["protocol"], "anthropic")

    def test_anthropic_truncation_tool_calls_and_invalid_usage_fail(self):
        provider = AnthropicCompatibleTextProvider(TextModelConfig(
            provider="custom", protocol="anthropic", base_url="https://example.com/v1", model="m", api_key="test"))
        for reason in ("max_tokens", "tool_use", "refusal"):
            install_response(provider, {"stop_reason": reason, "content": [{"type": "text", "text": "partial"}]})
            with self.assertRaises(ProviderError) as caught:
                provider.complete(TextRequest(prompt="x"))
            self.assertEqual(caught.exception.code, "provider_incomplete")
        for body in ({"stop_reason": "end_turn", "content": None},
                     {"stop_reason": "end_turn", "content": [{"type": "text", "text": "OK"}],
                      "usage": {"input_tokens": -1, "output_tokens": 2}}):
            install_response(provider, body)
            with self.assertRaises(ProviderError) as caught:
                provider.complete(TextRequest(prompt="x"))
            self.assertEqual(caught.exception.code, "provider_invalid_response")

    def test_factory_selects_protocol_independently_of_platform_name(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "providers.json"
            for protocol, adapter in (("openai", OpenAICompatibleTextProvider), ("anthropic", AnthropicCompatibleTextProvider)):
                path.write_text(json.dumps({"provider": "user-defined-platform", "protocol": protocol,
                                           "base_url": "https://example.com/v1", "model": "chosen-model",
                                           "api_key": "private-test-key"}), encoding="utf-8")
                with patch.dict(os.environ, {"KNOA_PARSE_PROVIDER_CONFIG": str(path)}, clear=True):
                    self.assertIsInstance(text_provider_from_env(), adapter)

    def test_wire_protocol_usage_and_vendor_parameters(self):
        provider = make_provider(enable_thinking=False)
        install_response(provider, headers={"x-siliconcloud-trace-id": "trace-test"})
        result = provider.complete(TextRequest(prompt="合成资料", max_tokens=32))
        req = provider.opener.open.call_args.args[0]
        wire = json.loads(req.data)
        self.assertEqual(req.full_url, "https://api.siliconflow.cn/v1/chat/completions")
        self.assertEqual(req.get_header("Authorization"), "Bearer private-test-key")
        self.assertEqual(wire["messages"][-1]["content"], "合成资料")
        self.assertFalse(wire["enable_thinking"])
        self.assertFalse(wire["stream"])
        self.assertEqual(result.usage.total_tokens, 15)
        self.assertEqual(result.request_id, "trace-test")
        self.assertEqual(result.acquisition, "inferred")
        self.assertNotIn("private-test-key", result.model_dump_json() + repr(provider.config) + str(provider.describe()))

    def test_switch_platform_without_vendor_specific_payload(self):
        provider = make_provider(provider="openai_compatible", base_url="https://example.com/api/v1", model="other-model")
        install_response(provider)
        provider.complete(TextRequest(prompt="test"))
        req = provider.opener.open.call_args.args[0]
        self.assertEqual(req.full_url, "https://example.com/api/v1/chat/completions")
        self.assertNotIn("enable_thinking", json.loads(req.data))

    def test_config_environment_overrides_and_safe_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "provider.json"
            path.write_text(json.dumps({"api_key": "private-test-key"}), encoding="utf-8")
            with patch.dict(os.environ, {"KNOA_PARSE_PROVIDER_CONFIG": str(path),
                                        "KNOA_PARSE_MODEL_MODEL": "selected-model"}, clear=True):
                provider = text_provider_from_env()
                self.assertEqual(provider.describe()["model"], "selected-model")
                self.assertFalse(provider.config.enable_thinking)
            path.write_text('{"api_key": "private-test-key", "bad-option": 1}', encoding="utf-8")
            with patch.dict(os.environ, {"KNOA_PARSE_PROVIDER_CONFIG": str(path)}, clear=True):
                with self.assertRaises(ProviderError) as caught:
                    text_provider_from_env()
                self.assertEqual(caught.exception.code, "provider_config_invalid")
                self.assertNotIn("private-test-key", str(caught.exception))
            path.unlink()
            with patch.dict(os.environ, {"KNOA_PARSE_PROVIDER_CONFIG": str(path)}, clear=True):
                with self.assertRaises(ProviderError):
                    text_provider_from_env()

    def test_limits_reject_before_network(self):
        for options, request in (({"max_output_tokens": 32}, TextRequest(prompt="x", max_tokens=33)),
                                 ({"max_input_chars": 2}, TextRequest(prompt="abc"))):
            provider = make_provider(**options)
            install_response(provider)
            with self.assertRaises(ProviderError) as caught:
                provider.complete(request)
            self.assertEqual(caught.exception.code, "provider_resource_limit")
            provider.opener.open.assert_not_called()
        provider = make_provider(max_response_bytes=8)
        install_response(provider, b"x" * 9)
        with self.assertRaises(ProviderError) as caught:
            provider.complete(TextRequest(prompt="x"))
        self.assertEqual(caught.exception.code, "provider_response_limit")

    def test_errors_are_stable_redacted_and_never_automatically_retried(self):
        for status, code, retryable in ((401, "provider_authentication", False), (402, "provider_quota", False),
                                         (403, "provider_forbidden", False), (404, "provider_model_unavailable", False),
                                         (429, "provider_rate_limit", True), (503, "provider_http_error", True),
                                         (302, "provider_http_error", False)):
            provider = make_provider()
            provider.opener = Mock()
            provider.opener.open.side_effect = HTTPError("https://example.com", status, "private-test-key", {},
                                                        io.BytesIO(b"private-test-key"))
            with self.assertRaises(ProviderError) as caught:
                provider.complete(TextRequest(prompt="x"))
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.retryable, retryable)
            self.assertNotIn("private-test-key", str(caught.exception))
            self.assertEqual(provider.opener.open.call_count, 1)
        for error, code in ((socket.timeout(), "provider_timeout"),
                            (URLError(socket.timeout()), "provider_timeout"),
                            (URLError("private-test-key"), "provider_unavailable")):
            provider.opener.open.reset_mock()
            provider.opener.open.side_effect = error
            with self.assertRaises(ProviderError) as caught:
                provider.complete(TextRequest(prompt="x"))
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(provider.opener.open.call_count, 1)

    def test_incomplete_and_malformed_answers_do_not_become_success(self):
        for body, code in ((b"not json", "provider_invalid_response"), ({"choices": []}, "provider_invalid_response"),
                           ({"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}, "provider_incomplete"),
                           ({"choices": [{"message": {"content": None}, "finish_reason": "stop"}]}, "provider_incomplete"),
                           ({"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                             "usage": {"total_tokens": -1}}, "provider_invalid_response")):
            provider = make_provider()
            install_response(provider, body)
            with self.assertRaises(ProviderError) as caught:
                provider.complete(TextRequest(prompt="x"))
            self.assertEqual(caught.exception.code, code)

    def test_no_redirect_or_insecure_credentials(self):
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.com"))
        for url in ("http://example.com/v1", "https://key@example.com/v1", "https://example.com?key=secret"):
            with self.assertRaises(ValueError):
                make_provider(base_url=url)
        for options in ({"api_key": 123}, {"enable_thinking": "false"}, {"timeout_seconds": float("nan")},
                        {"max_output_tokens": True}):
            with self.assertRaises(ValueError):
                make_provider(**options)


try:
    from fastapi.testclient import TestClient
    from knoa_parse.apps.api import create_app
    from knoa_parse.core.settings import Settings
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "Install api extra")
class ModelApiTests(unittest.TestCase):
    def test_project_server_config_starts_api_without_environment_token(self):
        from knoa_parse.apps.api import create_from_env
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            path.write_text(json.dumps({"api_token": "configured-private-token", "data_dir": directory}), encoding="utf-8")
            with patch.dict(os.environ, {"KNOA_PARSE_SERVER_CONFIG": str(path)}, clear=True), \
                    patch("knoa_parse.apps.api.text_provider_from_env", return_value=None):
                client = TestClient(create_from_env())
                self.assertEqual(client.get("/v1/capabilities").status_code, 200)
                response = client.get("/v1/capabilities", headers={"Authorization": "Bearer configured-private-token"})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("configured-private-token", response.text)
                self.assertEqual(server_configuration().data_dir, Path(directory))
                with patch.dict(os.environ, {"KNOA_PARSE_API_TOKEN": "override-token"}):
                    self.assertEqual(server_configuration().data_dir, Path(directory))
                    self.assertEqual(TestClient(create_from_env()).get("/v1/jobs").status_code, 200)

    def test_invalid_server_config_does_not_expose_secrets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.json"
            for body in ('{"api_token": "private-token", "unknown": 1}', '{"data_dir": 123}',
                         '{"api_token": "private-token", "data_dir": ""}', '{bad private-token'):
                path.write_text(body, encoding="utf-8")
                with patch.dict(os.environ, {"KNOA_PARSE_SERVER_CONFIG": str(path)}, clear=True):
                    with self.assertRaises(RuntimeError) as caught:
                        server_configuration()
                    self.assertNotIn("private-token", str(caught.exception))

    def test_authenticated_injected_provider_and_missing_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = make_provider()
            install_response(provider)
            client = TestClient(create_app(Settings(Path(directory)), "local-token", text_provider=provider))
            auth = {"Authorization": "Bearer local-token"}
            self.assertEqual(client.post("/v1/models/text", json={"prompt": "test"}).status_code, 401)
            provider.opener.open.assert_not_called()
            caps = client.get("/v1/capabilities", headers=auth).json()
            self.assertEqual(caps["external_capabilities"][0]["provider"], "siliconflow")
            self.assertNotIn("private-test-key", json.dumps(caps))
            for body in ({"prompt": "test", "api_key": "not-accepted"}, {"prompt": ""},
                         {"prompt": "test", "max_tokens": 4097}):
                self.assertEqual(client.post("/v1/models/text", json=body, headers=auth).status_code, 422)
            self.assertEqual(client.post("/v1/models/text", content=b"x" * 200000, headers=auth).status_code, 413)
            provider.opener.open.assert_not_called()
            result = client.post("/v1/models/text", json={"prompt": "test"}, headers=auth)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["usage"]["total_tokens"], 15)
            self.assertNotIn("private-test-key", result.text)
            empty = TestClient(create_app(Settings(Path(directory)), "local-token"))
            self.assertEqual(empty.post("/v1/models/text", json={"prompt": "test"}, headers=auth).status_code, 503)

    def test_provider_failure_public_error(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = make_provider()
            provider.opener = Mock()
            provider.opener.open.side_effect = socket.timeout()
            client = TestClient(create_app(Settings(Path(directory)), "local-token", text_provider=provider))
            response = client.post("/v1/models/text", json={"prompt": "test"},
                                   headers={"Authorization": "Bearer local-token"})
            self.assertEqual(response.status_code, 504)
            self.assertTrue(response.json()["error"]["retryable"])


if __name__ == "__main__":
    unittest.main()
