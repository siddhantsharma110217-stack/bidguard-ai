"""Live Claude implementation of AIProvider.

Not exercised by the default demo path (AI_PROVIDER=mock). Selected by
setting AI_PROVIDER=anthropic and ANTHROPIC_API_KEY in .env. Responses are
cached to SQLite by prompt hash so repeated runs during development don't
re-spend tokens.
"""

import json

import anthropic

from app.ai.cache import get_cached, hash_prompt, set_cached
from app.config import settings


class AnthropicProvider:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.ai_model

    def complete_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: dict,
        cache_key: str | None = None,
    ) -> dict:
        prompt_hash = hash_prompt(cache_key or task, self._model, prompt)
        cached = get_cached(prompt_hash)
        if cached is not None:
            return cached

        response = self._client.messages.create(
            model=self._model,
            max_tokens=8000,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are the document-analysis engine inside BidGuard AI, "
                        "a GeM procurement bid-compliance platform. You extract and "
                        "classify facts from tender and bid documents strictly and "
                        "literally. Never invent facts that are not present in the "
                        "supplied text. If information is absent, say so explicitly "
                        "rather than guessing."
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": prompt}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": schema},
            },
        )

        text = next(b.text for b in response.content if b.type == "text")
        data = json.loads(text)

        set_cached(
            prompt_hash,
            self._model,
            data,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
        return data
