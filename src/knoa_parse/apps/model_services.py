"""Composition and private configuration; consumers depend on the core port only."""
import json
import os
from pathlib import Path

from knoa_parse.core.text_model import ProviderError, TextModelProvider
from knoa_parse.providers.text_model.openai_compatible import OpenAICompatibleTextProvider
from knoa_parse.providers.text_model.anthropic_compatible import AnthropicCompatibleTextProvider
from knoa_parse.providers.text_model.transport import TextModelConfig


def build_text_provider(config: dict) -> TextModelProvider:
    provider = config.get("provider", "siliconflow")
    protocol = config.get("protocol", "anthropic" if provider == "anthropic_compatible" else "openai")
    defaults = {"base_url": "https://api.siliconflow.cn/v1", "model": "deepseek-ai/DeepSeek-V3.2",
                "enable_thinking": False} if provider == "siliconflow" and protocol == "openai" else {}
    settings = TextModelConfig(**{"provider": provider, **defaults, **config, "protocol": protocol})
    adapter = {"openai": OpenAICompatibleTextProvider, "anthropic": AnthropicCompatibleTextProvider}[protocol]
    return adapter(settings)


def text_provider_from_env() -> TextModelProvider | None:
    path = Path(os.getenv("KNOA_PARSE_PROVIDER_CONFIG", ".local/providers.json"))
    try:
        if not path.exists() and "KNOA_PARSE_PROVIDER_CONFIG" in os.environ:
            raise ValueError("Explicit provider config file does not exist")
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(config, dict):
            raise ValueError("Provider config must be an object")
        for key in ("provider", "protocol", "base_url", "model", "api_key", "timeout_seconds", "enable_thinking", "anthropic_version"):
            value = os.getenv("KNOA_PARSE_MODEL_" + key.upper())
            if value is not None:
                config[key] = json.loads(value) if key in {"timeout_seconds", "enable_thinking"} else value
        if not config:
            return None
        return build_text_provider(config)
    except (OSError, ValueError, TypeError):
        # Do not interpolate configuration/validation errors: these may include credentials.
        raise ProviderError("provider_config_invalid", "Invalid model service configuration; check local settings", 503) from None


def require_text_provider(provider: TextModelProvider | None) -> TextModelProvider:
    if provider is None:
        raise ProviderError("capability_missing", "Configure a text model provider before requesting generation", 503)
    return provider
