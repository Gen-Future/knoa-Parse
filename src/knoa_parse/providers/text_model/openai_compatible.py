"""Chat Completions adapter for managed OpenAI-compatible services."""
import json
from urllib.request import build_opener

from knoa_parse.core.text_model import ProviderError, TextRequest, TextResponse, TokenUsage
from .transport import NoRedirect, TextModelConfig, post_json


class OpenAICompatibleTextProvider:
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
        payload = {"model": c.model, "messages": [{"role": "system", "content": request.system},
                   {"role": "user", "content": request.prompt}], "stream": False,
                   "max_tokens": request.max_tokens}
        if c.enable_thinking is not None:
            payload["enable_thinking"] = c.enable_thinking
        body, trace = post_json(c, self.opener, "/chat/completions", payload,
                                {"Authorization": "Bearer " + c.api_key})
        try:
            data = json.loads(body)
            choice = data["choices"][0]
            text = choice["message"]["content"]
            reason = choice["finish_reason"]
            if not isinstance(text, str) or not text.strip() or reason != "stop":
                raise ProviderError("provider_incomplete", "Model did not return a complete text answer")
            usage = data.get("usage") or {}
            return TextResponse(provider=c.provider, model=data.get("model") or c.model, text=text,
                                finish_reason=reason, request_id=trace or data.get("id"),
                                usage=TokenUsage(**{key: usage.get(key) for key in
                                                 ("prompt_tokens", "completion_tokens", "total_tokens")}))
        except (ValueError, KeyError, IndexError, TypeError, AttributeError, RecursionError):
            raise ProviderError("provider_invalid_response", "Model service returned an invalid response") from None
