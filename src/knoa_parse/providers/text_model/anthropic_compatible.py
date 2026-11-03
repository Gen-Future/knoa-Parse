"""Messages API adapter; callers continue using the supplier-neutral core port."""
import json
from urllib.request import build_opener

from knoa_parse.core.text_model import ProviderError, TextRequest, TextResponse, TokenUsage
from .transport import NoRedirect, TextModelConfig, post_json


class AnthropicCompatibleTextProvider:
    def __init__(self, config: TextModelConfig):
        self.config = config
        self.opener = build_opener(NoRedirect())

    def describe(self) -> dict:
        c = self.config
        return {"capability": "text_model", "provider": c.provider, "protocol": c.protocol, "model": c.model,
                "external_service": True, "streaming": False, "max_input_chars": c.max_input_chars,
                "max_output_tokens": c.max_output_tokens, "timeout_seconds": c.timeout_seconds}

    def complete(self, request: TextRequest) -> TextResponse:
        c = self.config
        if len(request.prompt) + len(request.system) > c.max_input_chars or request.max_tokens > c.max_output_tokens:
            raise ProviderError("provider_resource_limit", "Request exceeds configured model limits", 413)
        payload = {"model": c.model, "system": request.system,
                   "messages": [{"role": "user", "content": request.prompt}],
                   "max_tokens": request.max_tokens, "stream": False}
        body, trace = post_json(c, self.opener, "/messages", payload,
                                {"x-api-key": c.api_key, "anthropic-version": c.anthropic_version})
        try:
            data = json.loads(body)
            blocks = data["content"]
            if not isinstance(blocks, list):
                raise ValueError("Invalid content blocks")
            text = "".join(block["text"] for block in blocks if block["type"] == "text")
            if not text.strip() or data["stop_reason"] not in {"end_turn", "stop_sequence"}:
                raise ProviderError("provider_incomplete", "Model did not return a complete text answer")
            usage = data.get("usage") or {}
            counts = TokenUsage(prompt_tokens=usage.get("input_tokens"), completion_tokens=usage.get("output_tokens"))
            prompt, completion = counts.prompt_tokens, counts.completion_tokens
            cache = [usage.get("cache_creation_input_tokens", 0), usage.get("cache_read_input_tokens", 0)]
            if any(type(value) is not int or value < 0 for value in cache):
                raise ValueError("Invalid cache token usage")
            if prompt is not None:
                prompt += sum(cache)
            total = None
            if prompt is not None and completion is not None:
                total = prompt + completion
            return TextResponse(provider=c.provider, model=data.get("model") or c.model, text=text,
                                finish_reason="stop", request_id=trace or data.get("id"),
                                usage=TokenUsage(prompt_tokens=prompt, completion_tokens=completion, total_tokens=total))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderError("provider_invalid_response", "Model service returned an invalid response") from None
