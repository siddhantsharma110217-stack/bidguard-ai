"""Verification adapters and the statuses they produce.

An adapter answers two questions: `can_verify(requirement)` (is this the kind
of document it knows how to check?) and `verify(submitted)` (does the issuer
record confirm the submitted details?). Only the mock BIS adapter exists; a
real issuer integration would implement the same interface.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from app.verification.registry import MockIssuerRegistry, normalise_company, normalise_number

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
VERIFICATION_FAILED = "VERIFICATION_FAILED"
NOT_APPLICABLE = "NOT_APPLICABLE"
STATUSES = (VERIFIED, UNVERIFIED, VERIFICATION_FAILED, NOT_APPLICABLE)

FAILED_LABEL = "Verification failed — officer review required"


@dataclass
class FieldCheck:
    field: str
    label: str
    submitted: str
    issuer: str


@dataclass
class Submitted:
    certificate_number: str
    holder: str
    holder_source: str  # where the holder name came from
    document_id: int | None = None
    document_name: str = ""
    page: int = 0


@dataclass
class VerificationResult:
    status: str
    reason: str  # a full sentence, shown to people
    clause: str  # the same reason as a clause, for "Evidence meets ..., but <clause>."
    source: str = ""
    checked_at: str = ""
    matched: list[FieldCheck] = field(default_factory=list)
    mismatched: list[FieldCheck] = field(default_factory=list)
    issuer_record: dict | None = None
    submitted: dict | None = None

    def details(self) -> dict:
        return {
            "matched": [asdict(f) for f in self.matched],
            "mismatched": [asdict(f) for f in self.mismatched],
            "issuer_record": self.issuer_record,
            "submitted": self.submitted,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def not_applicable(reason: str) -> VerificationResult:
    return VerificationResult(status=NOT_APPLICABLE, reason=reason, clause=reason[0].lower() + reason[1:].rstrip("."))


class VerificationAdapter(Protocol):
    source_name: str

    def can_verify(self, requirement) -> bool: ...

    def verify(self, submitted: Submitted) -> VerificationResult: ...


def _number_check(submitted: Submitted, record) -> FieldCheck:
    return FieldCheck(
        "certificate_number", "Certificate number", submitted.certificate_number, record.certificate_number
    )


def _holder_check(submitted: Submitted, record) -> FieldCheck:
    return FieldCheck("holder", "Certificate holder", submitted.holder, record.holder)


class BisCertificateAdapter:
    """Checks a BIS registration number and holder against the mock registry."""

    FIELDS = ("bis_registration_no",)

    def __init__(self, registry: MockIssuerRegistry | None = None) -> None:
        self.registry = registry or MockIssuerRegistry()
        self.source_name = self.registry.source_name

    def can_verify(self, requirement) -> bool:
        return (requirement.rule_params or {}).get("field") in self.FIELDS

    def verify(self, submitted: Submitted) -> VerificationResult:
        base = {
            "source": self.source_name,
            "checked_at": now_iso(),
            "submitted": {
                "certificate_number": submitted.certificate_number,
                "holder": submitted.holder,
                "holder_source": submitted.holder_source,
                "document_name": submitted.document_name,
                "page": submitted.page,
            },
        }
        if not normalise_number(submitted.certificate_number):
            return VerificationResult(
                status=UNVERIFIED,
                reason="No certificate number could be read from the document, so it could not be checked against the issuer record.",
                clause="no certificate number could be read from the document to check against the issuer record",
                **base,
            )

        record = self.registry.by_number(submitted.certificate_number)
        if record is not None:
            issuer = asdict(record)
            if normalise_company(record.holder) == normalise_company(submitted.holder):
                return VerificationResult(
                    status=VERIFIED,
                    reason="The certificate number and holder match the issuer record.",
                    clause="the certificate number and holder match the issuer record",
                    matched=[_number_check(submitted, record), _holder_check(submitted, record)],
                    issuer_record=issuer,
                    **base,
                )
            return VerificationResult(
                status=VERIFICATION_FAILED,
                reason="The issuer record for this certificate number names a different company.",
                clause="the issuer record for this certificate number names a different company",
                matched=[_number_check(submitted, record)],
                mismatched=[_holder_check(submitted, record)],
                issuer_record=issuer,
                **base,
            )

        record = self.registry.by_holder(submitted.holder)
        if record is not None:
            return VerificationResult(
                status=VERIFICATION_FAILED,
                reason="The certificate number does not match the issuer record for this company.",
                clause="the certificate number does not match the issuer record",
                matched=[_holder_check(submitted, record)],
                mismatched=[_number_check(submitted, record)],
                issuer_record=asdict(record),
                **base,
            )

        return VerificationResult(
            status=UNVERIFIED,
            reason="No issuer record is available for this certificate number.",
            clause="no issuer record is available for this certificate number",
            **base,
        )


def get_adapters() -> list[VerificationAdapter]:
    return [BisCertificateAdapter()]
