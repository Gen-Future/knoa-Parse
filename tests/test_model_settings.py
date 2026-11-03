import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knoa_parse.apps.model_services import build_text_provider
from knoa_parse.apps.model_settings import ModelSettingsManager, ModelSettingsRequest
from knoa_parse.core.text_model import ProviderError


def initial_config():
    return {"provider": "siliconflow", "protocol": "openai", "base_url": "https://api.siliconflow.cn/v1",
            "model": "deepseek-ai/DeepSeek-V3.2", "api_key": "private-original-key", "enable_thinking": False}


class ModelSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "providers.json"
        self.path.write_text(json.dumps(initial_config()), encoding="utf-8")
        self.manager = ModelSettingsManager(self.path, build_text_provider(initial_config()))

    def test_preserves_hidden_key_and_updates_live_provider_and_file(self):
        before = self.manager.describe()
        self.assertTrue(before["key_configured"])
        self.assertNotIn("private-original-key", json.dumps(before))
        request = ModelSettingsRequest(model="new-model")
        result = self.manager.update(request)
        self.assertEqual(result["model"], "new-model")
        self.assertEqual(self.manager.provider.describe()["model"], "new-model")
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["api_key"], "private-original-key")
        self.assertEqual(saved["model"], "new-model")
        self.assertEqual(list(self.path.parent.glob(".provider-*")), [])

    def test_channel_change_requires_new_key_and_does_not_mutate_old_config(self):
        previous = self.path.read_bytes()
        for changes in ({"base_url": "https://other.example/v1"}, {"provider": "custom"}, {"protocol": "anthropic"}):
            with self.assertRaises(ProviderError) as caught:
                self.manager.update(ModelSettingsRequest(**changes))
            self.assertEqual(caught.exception.code, "provider_key_required")
            self.assertEqual(self.path.read_bytes(), previous)
        result = self.manager.update(ModelSettingsRequest(provider="custom", protocol="anthropic",
                                     base_url="https://other.example/v1", model="custom-model", api_key="private-new-key"))
        self.assertEqual(result["protocol"], "anthropic")
        self.assertNotIn("private-new-key", json.dumps(result))
        self.assertIsNone(self.manager.provider.config.enable_thinking)

    def test_invalid_settings_and_failed_write_preserve_active_provider(self):
        previous = self.path.read_bytes()
        for request in (ModelSettingsRequest(base_url="http://insecure.example/v1", api_key="private-new-key"),
                        ModelSettingsRequest(api_key="invalid\nprivate-key")):
            with self.assertRaises(ProviderError):
                self.manager.update(request)
            self.assertEqual(self.path.read_bytes(), previous)
        with patch("knoa_parse.apps.model_settings.os.replace", side_effect=OSError("private-new-key")):
            with self.assertRaises(ProviderError) as caught:
                self.manager.update(ModelSettingsRequest(model="new-model"))
        self.assertEqual(caught.exception.code, "provider_config_write_failed")
        self.assertNotIn("private-new-key", str(caught.exception))
        self.assertEqual(self.manager.provider.config.model, "deepseek-ai/DeepSeek-V3.2")
        self.assertEqual(list(self.path.parent.glob(".provider-*")), [])

    def test_environment_overrides_lock_editor(self):
        self.manager.editable = False
        self.assertFalse(self.manager.describe()["editable"])
        with self.assertRaises(ProviderError) as caught:
            self.manager.update(ModelSettingsRequest())
        self.assertEqual(caught.exception.status_code, 409)


try:
    from fastapi.testclient import TestClient
    from knoa_parse.apps.api import create_app
    from knoa_parse.core.settings import Settings
except ImportError:
    TestClient = None


@unittest.skipIf(TestClient is None, "Install api extra")
class ModelSettingsApiTests(ModelSettingsTests):
    def test_demo_model_settings_can_be_read_and_saved_without_auth(self):
        client = TestClient(create_app(Settings(Path(self.temp.name) / "data"), model_settings=self.manager))
        self.assertEqual(client.get("/v1/settings/model").status_code, 200)
        response = client.put("/v1/settings/model", json={"model": "demo-model"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get("/v1/capabilities").json()["external_capabilities"][0]["model"], "demo-model")
        self.assertNotIn("private-original-key", response.text)

    def test_settings_are_authenticated_redacted_and_effective_without_restart(self):
        client = TestClient(create_app(Settings(Path(self.temp.name) / "data"), "test-token", model_settings=self.manager))
        headers = {"Authorization": "Bearer test-token"}
        for method, endpoint in (("GET", "/v1/settings/model"), ("PUT", "/v1/settings/model"),
                                 ("POST", "/v1/settings/model/test")):
            self.assertEqual(client.request(method, endpoint).status_code, 401)
        public = client.get("/v1/settings/model", headers=headers)
        self.assertNotIn("private-original-key", public.text)
        response = client.put("/v1/settings/model", json={"model": "updated-model"}, headers=headers)
        self.assertEqual(response.status_code, 200)
        caps = client.get("/v1/capabilities", headers=headers).json()
        self.assertEqual(caps["external_capabilities"][0]["model"], "updated-model")
        self.assertNotIn("private-original-key", response.text)

    def test_bad_key_input_never_echoes_validation_values(self):
        client = TestClient(create_app(Settings(Path(self.temp.name) / "data"), "test-token", model_settings=self.manager))
        headers = {"Authorization": "Bearer test-token"}
        response = client.put("/v1/settings/model", json={"api_key": "private-submitted-key", "protocol": "invalid"}, headers=headers)
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("private-submitted-key", response.text)
        response = client.put("/v1/settings/model", content=b"x" * 16385, headers=headers)
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
