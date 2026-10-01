"""Deterministic rule-based compliance evaluator.

This is a genuine evaluator, not a lookup table of canned verdicts: it
reads the structured fields extracted from each bidder document and
applies the requirement's own rule (`rule_type` + `rule_params`) to decide
the verdict. Feeding it different document values produces different
results, which is what makes the demo defensible.

Verdict resolution order (first match wins):
  1. No document supplies the field           -> MISSING
  2. Field found but flagged ambiguous        -> REVIEW
  3. Field found, extraction confidence low   -> REVIEW
  4. Rule evaluates false                     -> FAIL
  5. Rule evaluates true                      -> PASS
"""

from app.evaluation.evaluator import EvaluationOutcome
from app.evaluation.scoring import score_for_verdict

LOW_CONFIDENCE_THRESHOLD = 0.70

# Processor tiers, lowest to highest. Used by the `tier_min` rule.
PROCESSOR_TIERS = ["celeron", "pentium", "i3", "ryzen 3", "i5", "ryzen 5", "i7", "ryzen 7", "i9"]


class MockComplianceEvaluator:
    """Offline, deterministic ComplianceEvaluator implementation."""

    def evaluate_bid(self, requirements: list, documents: list) -> list[EvaluationOutcome]:
        outcomes = []
        for req in requirements:
            outcome = self._evaluate_one(req, documents)
            # Uploaded documents record how each value was extracted; carry
            # that into the trace so every evidence item can show it. Seeded
            # demo documents have neither key, so their traces are unchanged.
            data, _ = self._find_field((req.rule_params or {}).get("field", ""), documents)
            for key in ("extraction_method", "citation_status"):
                if data and data.get(key):
                    outcome.rule_trace[key] = data[key]
            outcomes.append(outcome)
        return outcomes

    # ---------- field lookup ----------

    def _find_field(self, field_name: str, documents: list):
        """Return (field_data, document) for the first doc supplying the field.

        Documents are searched in a stable order (by id) so results never
        depend on iteration order.
        """
        for doc in sorted(documents, key=lambda d: d.id):
            fields = doc.fields or {}
            if field_name in fields:
                return fields[field_name], doc
        return None, None

    # ---------- rule checks ----------

    def _check(self, rule_type: str, params: dict, data: dict) -> tuple[bool, dict]:
        """Apply one rule. Returns (passed, trace)."""
        if rule_type == "numeric_min":
            observed = data.get("numeric")
            threshold = params["threshold"]
            passed = observed is not None and observed >= threshold
            return passed, {
                "check": "numeric_min",
                "observed": observed,
                "required_minimum": threshold,
                "unit": params.get("unit", ""),
                "passed": passed,
            }

        if rule_type == "numeric_max":
            observed = data.get("numeric")
            threshold = params["threshold"]
            passed = observed is not None and observed <= threshold
            return passed, {
                "check": "numeric_max",
                "observed": observed,
                "required_maximum": threshold,
                "unit": params.get("unit", ""),
                "passed": passed,
            }

        if rule_type == "tier_min":
            value = str(data.get("value", "")).lower()
            minimum = params["minimum"].lower()
            observed_rank = self._tier_rank(value)
            required_rank = PROCESSOR_TIERS.index(minimum)
            passed = observed_rank is not None and observed_rank >= required_rank
            return passed, {
                "check": "tier_min",
                "observed": data.get("value"),
                "observed_tier": (
                    PROCESSOR_TIERS[observed_rank] if observed_rank is not None else None
                ),
                "required_minimum_tier": params["minimum"],
                "passed": passed,
            }

        if rule_type == "text_contains_any":
            value = str(data.get("value", "")).lower()
            options = params["options"]
            matched = [o for o in options if o.lower() in value]
            passed = bool(matched)
            return passed, {
                "check": "text_contains_any",
                "observed": data.get("value"),
                "accepted_values": options,
                "matched": matched,
                "passed": passed,
            }

        if rule_type == "presence":
            passed = bool(data.get("value"))
            return passed, {
                "check": "presence",
                "observed": data.get("value"),
                "passed": passed,
            }

        raise ValueError(f"Unknown rule_type: {rule_type}")

    def _tier_rank(self, value: str) -> int | None:
        """Highest tier keyword present in the value string."""
        best = None
        for idx, tier in enumerate(PROCESSOR_TIERS):
            if tier in value:
                best = idx if best is None else max(best, idx)
        return best

    # ---------- per-requirement evaluation ----------

    def _evaluate_one(self, req, documents: list) -> EvaluationOutcome:
        params = req.rule_params or {}
        field_name = params.get("field", "")
        expected = params.get("expected_display", "")

        data, doc = self._find_field(field_name, documents)

        # 1. Nothing in the package supplies this field.
        if data is None:
            return self._outcome(
                req,
                verdict="MISSING",
                confidence=0.99,
                evidence="",
                doc=None,
                page=0,
                explanation=(
                    f"No supporting evidence for '{req.title}' was found anywhere in the "
                    f"submitted document package. The bidder did not provide a document "
                    f"establishing {expected or 'this requirement'}."
                ),
                recommended_action=(
                    "Request the missing document from the bidder before technical "
                    "evaluation proceeds."
                ),
                decision_source="RULE",
                rule_trace={
                    "check": req.rule_type,
                    "field": field_name,
                    "observed": None,
                    "passed": False,
                    "reason": "field_not_present_in_any_document",
                },
            )

        confidence = float(data.get("confidence", 0.9))
        value = data.get("value", "")
        page = int(data.get("page", 0))
        snippet = data.get("snippet", value)

        # 2a. The evidence may sit on a page with no extractable text.
        if data.get("unreadable"):
            return self._outcome(
                req,
                verdict="REVIEW",
                confidence=0.0,
                evidence="",
                doc=doc,
                page=page,
                explanation=(
                    f"'{req.title}' is not stated on any readable page of the bid, but "
                    f"{data.get('ambiguity_reason', 'a page with no extractable text may hold the evidence')}. "
                    f"No automated verdict is issued."
                ),
                recommended_action=(
                    "Check the scanned page manually, or ask the bidder for a "
                    "text-searchable copy of the document."
                ),
                decision_source="HUMAN_REVIEW",
                rule_trace={
                    "check": req.rule_type,
                    "field": field_name,
                    "observed": None,
                    "passed": None,
                    "reason": "no_extractable_text",
                },
            )

        # 2b. Extraction flagged the evidence as ambiguous / incomplete.
        if data.get("ambiguous"):
            return self._outcome(
                req,
                verdict="REVIEW",
                confidence=confidence,
                evidence=snippet,
                doc=doc,
                page=page,
                explanation=(
                    f"Evidence for '{req.title}' was located in {doc.original_filename} "
                    f"but is incomplete or ambiguous: {data.get('ambiguity_reason', 'the document does not state the value unambiguously')}. "
                    f"An automated verdict cannot be issued safely."
                ),
                recommended_action=(
                    "Manual verification required. Ask the bidder for a clear, "
                    "current copy of this document."
                ),
                decision_source="HUMAN_REVIEW",
                rule_trace={
                    "check": req.rule_type,
                    "field": field_name,
                    "observed": value,
                    "passed": None,
                    "reason": "ambiguous_evidence",
                },
            )

        passed, trace = self._check(req.rule_type, params, data)
        trace["field"] = field_name

        # 3. Rule decided, but extraction confidence is too low to trust.
        if confidence < LOW_CONFIDENCE_THRESHOLD:
            return self._outcome(
                req,
                verdict="REVIEW",
                confidence=confidence,
                evidence=snippet,
                doc=doc,
                page=page,
                explanation=(
                    f"Evidence was extracted from {doc.original_filename} but with low "
                    f"confidence ({confidence:.0%}). The rule check is therefore not "
                    f"treated as conclusive."
                ),
                recommended_action="Manually confirm this value against the source document.",
                decision_source="HUMAN_REVIEW",
                rule_trace=trace,
            )

        # 4 / 5. Deterministic rule verdict.
        if passed:
            return self._outcome(
                req,
                verdict="PASS",
                confidence=confidence,
                evidence=snippet,
                doc=doc,
                page=page,
                explanation=self._pass_explanation(req, trace, doc, page),
                recommended_action="No action required.",
                decision_source="RULE",
                rule_trace=trace,
            )

        return self._outcome(
            req,
            verdict="FAIL",
            confidence=confidence,
            evidence=snippet,
            doc=doc,
            page=page,
            explanation=self._fail_explanation(req, trace, doc),
            recommended_action=(
                "This is a mandatory requirement and the bid does not meet it. "
                "Flag for rejection or seek written clarification."
                if req.obligation == "MANDATORY"
                else "Desirable requirement not met. Note during comparative scoring."
            ),
            decision_source="RULE",
            rule_trace=trace,
        )

    # ---------- explanation text ----------

    def _pass_explanation(self, req, trace: dict, doc, page: int) -> str:
        check = trace["check"]
        observed = trace.get("observed")
        src = doc.original_filename
        if check == "numeric_min":
            return (
                f"The bid offers {observed} {trace['unit']}, which meets or exceeds the "
                f"required minimum of {trace['required_minimum']} {trace['unit']} "
                # The page of the evidence, not of the tender clause.
                f"(source: {src}, page {page or 1})."
            )
        if check == "numeric_max":
            return (
                f"The bid commits to {observed} {trace['unit']}, within the permitted "
                f"maximum of {trace['required_maximum']} {trace['unit']} (source: {src})."
            )
        if check == "tier_min":
            return (
                f"The bidder specifies {observed}, satisfying the minimum processor "
                f"requirement of {trace['required_minimum_tier']} or higher (source: {src})."
            )
        if check == "text_contains_any":
            return (
                f"The bid states '{observed}', which matches the accepted value "
                f"'{trace['matched'][0]}' (source: {src})."
            )
        return f"Required evidence '{observed}' was located in {src}."

    def _fail_explanation(self, req, trace: dict, doc) -> str:
        check = trace["check"]
        observed = trace.get("observed")
        src = doc.original_filename
        if check == "numeric_min":
            return (
                f"The bid offers {observed} {trace['unit']}, which is below the required "
                f"minimum of {trace['required_minimum']} {trace['unit']}. "
                f"Shortfall: {trace['required_minimum'] - observed} {trace['unit']} "
                f"(source: {src})."
            )
        if check == "numeric_max":
            return (
                f"The bid commits to {observed} {trace['unit']}, exceeding the permitted "
                f"maximum of {trace['required_maximum']} {trace['unit']} by "
                f"{observed - trace['required_maximum']} {trace['unit']} (source: {src})."
            )
        if check == "tier_min":
            return (
                f"The bidder offers {observed}, which is below the required minimum "
                f"processor tier of {trace['required_minimum_tier']} (source: {src})."
            )
        if check == "text_contains_any":
            return (
                f"The bid states '{observed}', which does not match any accepted value "
                f"({', '.join(trace['accepted_values'])}) (source: {src})."
            )
        return f"The requirement was not satisfied by the evidence in {src}."

    # ---------- assembly ----------

    def _outcome(
        self,
        req,
        *,
        verdict: str,
        confidence: float,
        evidence: str,
        doc,
        page: int,
        explanation: str,
        recommended_action: str,
        decision_source: str,
        rule_trace: dict,
    ) -> EvaluationOutcome:
        return EvaluationOutcome(
            requirement_id=req.id,
            requirement_code=req.code,
            requirement_title=req.title,
            category=req.category,
            obligation=req.obligation,
            expected_condition=(req.rule_params or {}).get("expected_display", ""),
            verdict=verdict,
            score=score_for_verdict(verdict),
            confidence=round(confidence, 2),
            evidence=evidence,
            source_document=doc.original_filename if doc else "",
            source_document_id=doc.id if doc else None,
            source_page=page,
            explanation=explanation,
            recommended_action=recommended_action,
            decision_source=decision_source,
            rule_trace=rule_trace,
        )
