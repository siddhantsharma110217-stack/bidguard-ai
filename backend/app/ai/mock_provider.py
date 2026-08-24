"""Offline, deterministic stand-in for a real AI provider.

Fixtures live at `app/ai/fixtures/{task}/{cache_key}.json`. Pipeline code
calls `complete_json` exactly as it would against a live model; the mock
provider just resolves the response from disk instead of the network, so
the demo runs with zero external dependencies and zero API cost.

Populated with real fixture files in Phase 3 (requirement extraction,
document classification, field extraction, adjudication).
"""

import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class FixtureNotFound(RuntimeError):
    pass


class MockProvider:
    def complete_json(
        self,
        *,
        task: str,
        prompt: str,
        schema: dict,
        cache_key: str | None = None,
    ) -> dict:
        key = cache_key or "default"
        path = FIXTURES_DIR / task / f"{key}.json"
        if not path.exists():
            raise FixtureNotFound(
                f"No mock fixture for task='{task}' cache_key='{key}' "
                f"(expected {path}). Add one under app/ai/fixtures/{task}/."
            )
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
