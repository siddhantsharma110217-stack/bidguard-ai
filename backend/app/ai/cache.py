import hashlib

from app.db import SessionLocal
from app.models import LLMCache


def hash_prompt(task: str, model: str, prompt: str) -> str:
    raw = f"{model}\n{task}\n{prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_cached(prompt_hash: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.get(LLMCache, prompt_hash)
        return row.response if row else None
    finally:
        db.close()


def set_cached(
    prompt_hash: str, model: str, response: dict, tokens_in: int = 0, tokens_out: int = 0
) -> None:
    db = SessionLocal()
    try:
        existing = db.get(LLMCache, prompt_hash)
        if existing:
            return
        row = LLMCache(
            prompt_hash=prompt_hash,
            model=model,
            response=response,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        db.add(row)
        db.commit()
    finally:
        db.close()
