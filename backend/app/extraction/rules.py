"""Rule-based (deterministic, offline) evidence extraction.

Each requirement field of the demo tender has a pattern. Every line of
every page is scanned; each match becomes a candidate carrying its page and
the matched line as evidence. Then:

* one consistent value              -> clean evidence, high confidence
* different values (a conflict)     -> ambiguous, so the requirement is REVIEW
* a negated / qualified statement   -> ambiguous ("BIS certificate: applied for")
* a mention without a usable value  -> ambiguous ("MAF enclosed" with no ref.)
* nothing at all                    -> not found (MISSING, unless an unreadable
                                       page might hold it; see `service`)

This module never decides a verdict; it only reports what the text says.
"""

import re
from dataclasses import dataclass

CLEAN_SINGLE_CONFIDENCE = 0.95
CLEAN_REPEATED_CONFIDENCE = 0.92

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Statements that say the evidence is NOT (yet) provided.
NEGATION = re.compile(
    r"\b(not|no|nil|without|n/a|pending|awaited|applied for|under process|"
    r"to be (?:submitted|provided|furnished)|will be (?:submitted|provided|furnished))\b",
    re.I,
)
# Phrases containing "not"/"no" that are not negations of the evidence.
NOT_A_NEGATION = re.compile(
    r"\b(not later than|not more than|not exceeding|no\.|ref(?:erence)?\.? no|reg(?:istration)?\.? no)",
    re.I,
)
# Upgrade headroom is not what is offered: "16 GB (upgradable to 32 GB)".
CAPACITY_QUALIFIER = re.compile(r"\b(upgradable|upgradeable|expandable|up to|upto|extendable|optional)\b", re.I)


# A mention without a usable value (an index entry, a heading). It only
# matters when no real value is found anywhere; it never conflicts with one.
SOFT_PROBLEMS = {
    "a processor is mentioned but the model is not recognised",
    "BIS is mentioned without a registration number",
    "an OEM authorisation is mentioned without a reference number",
}


@dataclass
class Candidate:
    doc_index: int
    page: int  # 1-based
    line: str
    value: str
    numeric: float | None
    key: str  # what must agree across candidates
    problem: str = ""  # non-empty -> this candidate alone is ambiguous


@dataclass
class SourceDoc:
    filename: str
    pages: list[str]  # index 0 = page 1
    pages_without_text: list[int]


def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _num(text: str) -> float:
    text = text.lower()
    return float(NUMBER_WORDS[text]) if text in NUMBER_WORDS else float(text)


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def _negated(line: str) -> bool:
    return bool(NEGATION.search(NOT_A_NEGATION.sub(" ", line)))


# ---------------------------------------------------------------------------
# Per-field line matchers: line -> list of (value, numeric, key, problem)
# ---------------------------------------------------------------------------

PROCESSOR = re.compile(
    r"(intel\s+core\s+i[3579](?:[-\s]\d{4,5}[a-z]{0,2})?|core\s+i[3579](?:[-\s]\d{4,5}[a-z]{0,2})?"
    r"|amd\s+ryzen\s+[3579](?:\s+(?:pro\s+)?\d{4}[a-z]{0,2})?|ryzen\s+[3579](?:\s+(?:pro\s+)?\d{4}[a-z]{0,2})?"
    r"|intel\s+celeron(?:\s+\w*\d\w*)?|celeron(?:\s+\w*\d\w*)?|intel\s+pentium(?:\s+\w*\d\w*)?|pentium(?:\s+\w*\d\w*)?)",
    re.I,
)


def _processor(line: str):
    if not re.search(r"\b(processor|cpu)\b", line, re.I):
        return []
    found = PROCESSOR.findall(line)
    if not found:
        return [("", None, "", "a processor is mentioned but the model is not recognised")]
    out = []
    for m in found:
        value = _clean(m)
        key = re.sub(r"[^a-z0-9]", "", value.lower()).replace("intel", "").replace("amd", "")
        out.append((value, None, key, ""))
    return out


def _capacity(line: str, keyword: str, exclude: str, unit_re: str, scale: dict, unit: str):
    if not re.search(keyword, line, re.I) or (exclude and re.search(exclude, line, re.I)):
        return []
    offered = CAPACITY_QUALIFIER.split(line)[0]
    values = [(_num(n) * scale[u.lower()]) for n, u in re.findall(unit_re, offered, re.I)]
    distinct = sorted(set(values))
    if not distinct:
        return []
    if len(distinct) > 1:
        shown = ", ".join(_fmt(v) for v in distinct)
        return [("", None, "", f"one line states several different values ({shown})")]
    v = distinct[0]
    return [(f"{_fmt(v)} {unit}", v, _fmt(v), "")]


def _ram(line: str):
    return _capacity(
        line, r"\b(ram|memory)\b", r"\b(storage|ssd|hdd|graphics|vram|cache)\b",
        r"(\d{1,3})\s*(gb)\b", {"gb": 1}, "GB",
    )


def _storage(line: str):
    out = _capacity(
        line, r"\b(storage|ssd|hdd|nvme|solid state|hard (?:disk|drive))\b", r"\bram\b",
        r"(\d+(?:\.\d+)?)\s*(tb|gb)\b", {"gb": 1, "tb": 1000}, "GB",
    )
    hdd_only = re.search(r"\b(hdd|hard (?:disk|drive))\b", line, re.I) and not re.search(
        r"\b(ssd|nvme|solid state)\b", line, re.I
    )
    if out and hdd_only and not out[0][3]:
        value, numeric, key, _ = out[0]
        return [(value, numeric, key, "the storage offered is a hard disk (HDD), not an SSD")]
    return out


def _display(line: str):
    if not re.search(r"\b(display|screen|panel)\b", line, re.I):
        return []
    sizes = re.findall(r"(\d{2}(?:\.\d{1,2})?)\s*(?:\"|”|''|-?\s*inch(?:es)?\b|-?\s*in\b)", line, re.I)
    distinct = sorted({float(s) for s in sizes})
    if not distinct:
        return []
    if len(distinct) > 1:
        return [("", None, "", "one line states several display sizes")]
    v = distinct[0]
    return [(f"{_fmt(v)} inch", v, _fmt(v), "")]


OS = re.compile(
    r"(windows\s+1[01](?:\s+(?:pro(?:fessional)?|home|enterprise|education))?(?:\s+\d{2}-bit)?"
    r"|ubuntu(?:\s+\d{2}\.\d{2})?(?:\s+lts)?|free\s*dos|chrome\s*os|linux)",
    re.I,
)


def _os(line: str):
    out = []
    for m in OS.findall(line):
        value = _clean(m)
        edition = re.sub(r"\s+\d{2}-bit$", "", value.lower())
        edition = edition.replace("professional", "pro")
        out.append((value, None, edition, ""))
    return out


def _years(line: str):
    if not re.search(r"\bwarrant", line, re.I):
        return []
    found = re.findall(
        r"\(?\b(\d{1,2}|one|two|three|four|five)\)?\s*(?:\(\s*\w+\s*\)\s*)?(years?|yrs?|months?)\b",
        line, re.I,
    )
    values = sorted({_num(n) / (12 if u.lower().startswith("month") else 1) for n, u in found})
    if not values:
        return []
    if len(values) > 1:
        return [("", None, "", "one line states several warranty periods")]
    v = values[0]
    return [(f"{_fmt(v)} year{'' if v == 1 else 's'}", v, _fmt(v), "")]


def _delivery(line: str):
    if not re.search(r"\bdeliver", line, re.I):
        return []
    if re.search(r"\b(payment|invoice|validity|valid for|replacement|response|resolution|emd|bank)\b", line, re.I):
        return []
    found = re.findall(r"\(?\b(\d{1,3})\)?\s*(?:calendar\s+|working\s+)?(days?|weeks?)\b", line, re.I)
    values = sorted({_num(n) * (7 if u.lower().startswith("week") else 1) for n, u in found})
    if not values:
        return []
    if len(values) > 1:
        return [("", None, "", "one line states several delivery periods")]
    v = values[0]
    return [(f"{_fmt(v)} days", v, _fmt(v), "")]


def _bis(line: str):
    if not re.search(r"\b(bis|bureau of indian standards|crs)\b", line, re.I):
        return []
    numbers = re.findall(r"\b(R-\d{6,10})\b", line, re.I)
    if _negated(line):
        return [("", None, "", "the line says the BIS registration is not (yet) provided")]
    if not numbers:
        if re.search(r"\b(registration|certificate|licen[cs]e)\b", line, re.I):
            return [("", None, "", "BIS is mentioned without a registration number")]
        return []
    return [(n.upper(), None, n.upper(), "") for n in numbers]


def _oem(line: str):
    if not re.search(r"(manufacturer'?s?\s+authori[sz]ation|\bmaf\b|oem\s+authori[sz]ation)", line, re.I):
        return []
    if _negated(line):
        return [("", None, "", "the line says the OEM authorisation is not (yet) provided")]
    refs = re.findall(r"\b((?:MAF|OEM)[A-Z]*[/\-][\w/\-.]*\d[\w/\-.]*)", line, re.I)
    refs += re.findall(r"(?:ref(?:erence)?\.?\s*(?:no\.?)?|no\.)\s*[:\-]?\s*([A-Z0-9][\w/\-.]*\d[\w/\-.]*)", line, re.I)
    refs = [r.rstrip(".") for r in refs]
    if not refs:
        return [("", None, "", "an OEM authorisation is mentioned without a reference number")]
    return [(r, None, r.upper(), "") for r in dict.fromkeys(refs)]


ENERGY = re.compile(r"(energy\s*star(?:\s*\d+(?:\.\d+)?)?(?:\s+certified)?|bee\s*\d?\s*-?\s*star(?:\s+rated)?|\d\s*-?\s*star\s+bee(?:\s+rated)?)", re.I)


def _energy(line: str):
    found = ENERGY.findall(line)
    if not found:
        return []
    if _negated(line):
        return [("", None, "", "the line says the energy rating is not held")]
    out = []
    for m in found:
        value = _clean(m)
        key = "ENERGY STAR" if "energy" in value.lower() else "BEE"
        out.append((value, None, key, ""))
    return out


MATCHERS = {
    "processor": _processor,
    "ram_gb": _ram,
    "storage_gb": _storage,
    "display_inch": _display,
    "operating_system": _os,
    "warranty_years": _years,
    "delivery_days": _delivery,
    "bis_registration_no": _bis,
    "oem_authorization_ref": _oem,
    "energy_rating": _energy,
}


def parse_line(field: str, line: str) -> list[tuple]:
    """Matches for one field on one line (also used to check AI quotes)."""
    matcher = MATCHERS.get(field)
    return matcher(line) if matcher else []


def find_candidates(field: str, docs: list[SourceDoc]) -> list[Candidate]:
    out = []
    for d_idx, doc in enumerate(docs):
        for p_idx, text in enumerate(doc.pages):
            for raw in text.splitlines():
                line = _clean(raw)
                if not line:
                    continue
                for value, numeric, key, problem in parse_line(field, line):
                    out.append(Candidate(d_idx, p_idx + 1, line, value, numeric, key, problem))
    return out


def extract_field(field: str, docs: list[SourceDoc]) -> tuple[int, dict] | None:
    """Evidence for one requirement field: (document index, field data) or None."""
    if field not in MATCHERS:
        first = 0
        return first, {
            "value": "",
            "page": 0,
            "confidence": 0.0,
            "snippet": "",
            "ambiguous": True,
            "ambiguity_reason": (
                "rule-based extraction has no pattern for this requirement, so it "
                "must be checked manually"
            ),
            "extraction_method": "RULES",
        }

    candidates = find_candidates(field, docs)
    if not candidates:
        return None

    first = candidates[0]
    clean = [c for c in candidates if not c.problem]
    hard = [c for c in candidates if c.problem and c.problem not in SOFT_PROBLEMS]
    keys = {c.key for c in clean}

    def where(c: Candidate) -> str:
        return f"{docs[c.doc_index].filename} p.{c.page}"

    problem = ""
    if len(keys) > 1:
        shown = "; ".join(f"'{c.value}' ({where(c)})" for c in clean)
        problem = f"conflicting values found: {shown}"
    elif hard:
        problem = f"{hard[0].problem} ({where(hard[0])})"
    elif not clean:
        problem = f"{first.problem} ({where(first)})"

    if clean:
        candidates = clean if not hard else candidates
    chosen = clean[0] if clean else (hard[0] if hard else first)
    data = {
        "value": chosen.value,
        "page": chosen.page,
        "confidence": (
            CLEAN_SINGLE_CONFIDENCE if len(candidates) == 1 else CLEAN_REPEATED_CONFIDENCE
        ),
        "snippet": chosen.line,
        "extraction_method": "RULES",
        "match_count": len(candidates),
    }
    if chosen.numeric is not None:
        data["numeric"] = chosen.numeric
    if not clean and not hard:
        # Only mentions: a scanned page, if any, is the better explanation.
        data["mention_only"] = True
    if problem:
        data["ambiguous"] = True
        data["ambiguity_reason"] = problem
        data["confidence"] = 0.5
    return chosen.doc_index, data
