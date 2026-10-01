"""Choose the extraction mode, run it, and attach evidence to documents.

AI mode runs only when ANTHROPIC_API_KEY is set. Rule-based extraction is
the default without a key and the fallback whenever the AI call fails,
refuses, or returns malformed output. Either way the result is the same
per-field evidence the seeded demo documents carry, so the existing rule
engine evaluates uploaded bids exactly like the demo bidders.
"""

import logging
from dataclasses import dataclass, field

from app.config import settings
from app.extraction import ai, rules
from app.extraction.pdf import NO_TEXT_LABEL
from app.extraction.rules import SourceDoc

log = logging.getLogger(__name__)

MODE_LABELS = {
    "AI": "AI extraction",
    "RULES": "Rule-based extraction (no AI key)",
    "RULES_FALLBACK": "Rule-based extraction (AI extraction failed)",
}


def ai_configured() -> bool:
    return bool(settings.anthropic_api_key.strip())


def active_mode() -> str:
    return "AI" if ai_configured() else "RULES"


def get_extraction_provider():
    """The AIProvider used for extraction, or None when no key is configured."""
    if not ai_configured():
        return None
    from app.ai.anthropic_provider import AnthropicProvider

    return AnthropicProvider(model=settings.extraction_model)


@dataclass
class ExtractionResult:
    mode: str  # AI | RULES | RULES_FALLBACK
    note: str = ""
    # field name -> (document index, field data)
    fields: dict[str, tuple[int, dict]] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return MODE_LABELS[self.mode]


def _unreadable_placeholder(docs: list[SourceDoc]) -> tuple[int, dict] | None:
    """Evidence for a requirement not found in any readable text, when some
    page has no extractable text: it might be on that page, so REVIEW."""
    for d_idx, doc in enumerate(docs):
        if doc.pages_without_text:
            pages = ", ".join(str(p) for p in doc.pages_without_text)
            many = len(doc.pages_without_text) > 1
            return d_idx, {
                "value": "",
                "page": doc.pages_without_text[0],
                "confidence": 0.0,
                "snippet": "",
                "ambiguous": True,
                "unreadable": True,
                "ambiguity_reason": (
                    f"{doc.filename} page{'s' if many else ''} {pages} "
                    f"({NO_TEXT_LABEL}) may hold the evidence"
                ),
            }
    return None


def extract_bid(requirements: list, docs: list[SourceDoc], provider="auto") -> ExtractionResult:
    """Extract evidence for every requirement from the bid's documents.

    `provider` defaults to the configured one; tests pass a stand-in provider,
    or None to force rule-based mode.
    """
    if provider == "auto":
        provider = get_extraction_provider()

    found: dict[str, tuple[int, dict] | None]
    if provider is None:
        result = ExtractionResult(mode="RULES")
        found = {}
    else:
        try:
            found = ai.extract_with_ai(provider, requirements, docs)
            result = ExtractionResult(mode="AI", note=f"Model: {getattr(provider, 'model', '')}".strip())
        except Exception as exc:  # any failure -> deterministic fallback
            log.warning("AI extraction failed, falling back to rules: %s", exc)
            reason = str(exc) or type(exc).__name__
            result = ExtractionResult(
                mode="RULES_FALLBACK", note=f"AI extraction failed ({reason[:200]})"
            )
            found = {}

    placeholder = _unreadable_placeholder(docs)
    for req in requirements:
        name = (req.rule_params or {}).get("field", "")
        if not name:
            continue
        hit = found.get(name) if result.mode == "AI" else rules.extract_field(name, docs)
        if placeholder is not None and (hit is None or hit[1].get("mention_only")):
            hit = placeholder
        if hit is not None:
            d_idx, data = hit
            if isinstance(data.get("numeric"), float) and data["numeric"].is_integer():
                data = {**data, "numeric": int(data["numeric"])}
            if result.mode == "RULES_FALLBACK":
                data = {**data, "extraction_method": "RULES_FALLBACK"}
            result.fields[name] = (d_idx, data)

    # The certificate holder, read from the page the certificate number was
    # found on, for issuer verification (app.verification).
    bis = result.fields.get("bis_registration_no")
    if bis and not bis[1].get("unreadable"):
        d_idx, data = bis
        page = int(data.get("page", 0) or 0)
        if 1 <= page <= len(docs[d_idx].pages):
            holder = rules.find_certificate_holder(docs[d_idx].pages[page - 1])
            if holder:
                result.fields["certificate_holder"] = (d_idx, {
                    "value": holder[0],
                    "page": page,
                    "confidence": rules.CLEAN_SINGLE_CONFIDENCE,
                    "snippet": holder[1],
                    "extraction_method": "RULES",
                })

    # Contact details are always read with deterministic patterns (in AI
    # mode too): they feed Red Flags, not verdicts.
    for name, hit in rules.extract_contacts(docs).items():
        result.fields.setdefault(name, hit)
    return result


def classify(filename: str, text: str) -> str:
    """Best-effort document type from filename + text keywords."""
    hay = f"{filename}\n{text}".lower()
    scores = {
        "TECHNICAL_BID": sum(hay.count(k) for k in ("technical", "processor", "specification", "memory")),
        "COMMERCIAL_BID": sum(hay.count(k) for k in ("commercial", "delivery schedule", "payment terms")),
        "WARRANTY_CERTIFICATE": 2 * hay.count("warranty certificate"),
        "BIS_CERTIFICATE": 2 * hay.count("bureau of indian standards"),
        "OEM_AUTHORIZATION": 2 * hay.count("manufacturer authori"),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "BID_DOCUMENT"
