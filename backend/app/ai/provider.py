"""Provider-agnostic AI interface.

Every AI call in the pipeline goes through `AIProvider.complete_json`. Two
implementations exist: `MockProvider` (offline, deterministic, no API key)
and `AnthropicProvider` (real Claude calls). The pipeline code never talks
to either concretely — it only depends on this Protocol — so swapping
providers is a one-line change in `get_provider()`.
"""

from typing import Protocol

from app.config import settings


class AIProvider(Protocol):
    def complete_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: dict,
        cache_key: str | None = None,
        system: str | None = None,
    ) -> dict:
        """Return a dict that validates against `schema`.

        Args:
            task: short identifier for the call site, e.g.
                "extract_requirements", "classify_document",
                "extract_fields", "adjudicate". Used for cache
                namespacing and (for the mock provider) fixture lookup.
            prompt: the full prompt text.
            schema: JSON schema the response must satisfy.
            cache_key: optional explicit cache key; defaults to a hash
                of (task, prompt).
            system: optional system prompt replacing the provider default.

        Raises on any failure (network, refusal, truncated or invalid
        JSON) so callers can fall back to a deterministic path.
        """
        ...


_provider: AIProvider | None = None


def get_provider() -> AIProvider:
    global _provider
    if _provider is not None:
        return _provider

    if settings.ai_provider == "anthropic":
        from app.ai.anthropic_provider import AnthropicProvider

        _provider = AnthropicProvider()
    else:
        from app.ai.mock_provider import MockProvider

        _provider = MockProvider()

    return _provider
