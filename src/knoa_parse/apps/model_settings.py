"""Authenticated model settings, atomic private persistence and live provider replacement."""
import json
import os
import tempfile
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Literal

from pydantic import Field, SecretStr

from knoa_parse.core.models import Model
from knoa_parse.core.text_model import ProviderError
from .model_services import build_text_provider


class ModelSettingsRequest(Model):
    provider: str = Field(default="siliconflow", min_length=1, max_length=64)
    protocol: Literal["openai", "anthropic"] = "openai"
    base_url: str = Field(default="https://api.siliconflow.cn/v1", min_length=1, max_length=2048)
    model: str = Field(default="deepseek-ai/DeepSeek-V3.2", min_length=1, max_length=256)
    api_key: SecretStr | None = None
    timeout_seconds: int = Field(default=60, ge=1, le=300)
    enable_thinking: bool | None = None


class ModelSettingsManager:
    def __init__(self, path: Path, provider=None, editable: bool = True):
        self.path = path
        self.provider = provider
        self.editable = editable
        self.lock = RLock()

    def describe(self):
        with self.lock:
            config = self.provider.config if self.provider else None
            result = {name: getattr(config, name) for name in
                      ("provider", "protocol", "base_url", "model", "timeout_seconds", "enable_thinking")} if config else {
                          "provider": "siliconflow", "protocol": "openai", "base_url": "https://api.siliconflow.cn/v1",
                          "model": "deepseek-ai/DeepSeek-V3.2", "timeout_seconds": 60, "enable_thinking": False}
            return {**result, "key_configured": bool(config and config.api_key), "editable": self.editable}

    def update(self, request: ModelSettingsRequest):
        with self.lock:
            if not self.editable:
                raise ProviderError("provider_config_overridden", "Model environment overrides are active; edit those settings first", 409)
            previous = self.provider.config if self.provider else None
            same_channel = previous and (previous.provider, previous.protocol, previous.base_url.rstrip("/")) == (
                request.provider, request.protocol, request.base_url.rstrip("/"))
            key = request.api_key.get_secret_value() if request.api_key else ""
            if not key and same_channel:
                key = previous.api_key
            if not key:
                raise ProviderError("provider_key_required", "Enter an API key when configuring a new platform or endpoint", 422)
            config = asdict(previous) if previous else {}
            config.update(request.model_dump(exclude={"api_key"}))
            config["api_key"] = key
            try:
                provider = build_text_provider(config)
            except (ValueError, TypeError):
                raise ProviderError("provider_config_invalid", "Invalid platform settings; check protocol, HTTPS URL, model and limits", 422) from None
            temporary = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=".provider-", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                    json.dump(config, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            except OSError:
                raise ProviderError("provider_config_write_failed", "Could not save private model settings", 503) from None
            finally:
                if temporary:
                    Path(temporary).unlink(missing_ok=True)
            self.provider = provider
            return self.describe()
