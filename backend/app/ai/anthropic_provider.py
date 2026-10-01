"""Live Claude implementation of AIProvider.

Used for bid-evidence extraction whenever ANTHROPIC_API_KEY is set (see
app.extraction.service), and for the older AI_PROVIDER=anthropic path.
Responses are cached to SQLite by prompt hash so repeated runs during
development don't re-spend tokens. The API key stays server-side.
"""

import json

import anthropic

from app.ai.cache import get_cached, hash_prompt, set_cached
from app.config import settings

DEFAULT_SYSTEM = (
    "You are the document-analysis engine inside BidGuard AI, "
    "a GeM procurement bid-compliance platform. You extract and "
    "classify facts from tender and bid documents strictly and "
    "literally. Never invent facts that are not present in the "
    "supplied text. If information is absent, say so explicitly "
    "rather than guessing."
)

# Models that accept the server-side refusal fallback (`fallbacks: "default"`):
# if the model declines, the API re-runs the request on a fallback model.
_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class AIResponseError(RuntimeError):
    pass


class AnthropicProvider:
    def __init__(self, model: str | None = None) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.ai_model

    def complete_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: dict,
        cache_key: str | None = None,
        system: str | None = None,
    ) -> dict:
        system_text = system or DEFAULT_SYSTEM
        prompt_hash = hash_prompt(cache_key or task, self.model, system_text + "\n" + prompt)
        cached = get_cached(prompt_hash)
        if cached is not None:
            return cached

        params = dict(
            model=self.model,
            max_tokens=16000,
            system=[{"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        if self.model in _FALLBACK_MODELS:
            response = self._client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params
            )
        else:
            response = self._client.messages.create(**params)

        if response.stop_reason == "refusal":
            raise AIResponseError("the model declined the request")
        if response.stop_reason == "max_tokens":
            raise AIResponseError("the response was cut off at max_tokens")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise AIResponseError("the response contained no text")
        data = json.loads(text)  # JSONDecodeError -> caller falls back

        set_cached(
            prompt_hash,
            self.model,
            data,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
        return data
