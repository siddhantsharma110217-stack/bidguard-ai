"""Mock issuer registry: a deterministic, local stand-in for an issuer's
certificate lookup. No network calls.

DEMO DATA ONLY. Every record here is fictional and belongs to the
"Demo Certification Authority (fictional)". Lookups are designed to give the
demo bidders known outcomes:

  TechNova Systems     R-41190527  record matches               -> VERIFIED
  Bharat Digital       R-41052219  no record                    -> UNVERIFIED
  Apex Infotech        R-41087632  registry holds R-41087623 for
                                   Apex (same company)           -> VERIFICATION_FAILED
  Crestline Computers  R-41093340  record matches               -> VERIFIED
  Uploaded samples:
    Sahyadri (Arcadia Computing Ltd.)  R-41055321 matches       -> VERIFIED
    Vertex Peak (Arcadia Computing Ltd.) R-41099887 is held by
                          a different company                    -> VERIFICATION_FAILED
    Northwind: number only on a scanned page                     -> UNVERIFIED
"""

import re
from dataclasses import dataclass

SOURCE_NAME = "Demo Certification Authority (fictional)"


@dataclass(frozen=True)
class IssuerRecord:
    certificate_number: str
    holder: str
    scheme: str
    standard: str
    valid_until: str


_RECORDS = [
    IssuerRecord("R-41190527", "TechNova Systems Pvt. Ltd.", "BIS CRS", "IS 13252 (Part 1) : 2010", "31/12/2027"),
    IssuerRecord("R-41087623", "Apex Infotech Solutions", "BIS CRS", "IS 13252 (Part 1) : 2010", "31/03/2028"),
    IssuerRecord("R-41093340", "Crestline Computers LLP", "BIS CRS", "IS 13252 (Part 1) : 2010", "15/01/2028"),
    IssuerRecord("R-41055321", "Arcadia Computing Ltd.", "BIS CRS", "IS 13252 (Part 1) : 2010", "31/12/2027"),
    IssuerRecord("R-41099887", "Summit Ridge Computers Pvt. Ltd.", "BIS CRS", "IS 13252 (Part 1) : 2010", "30/06/2027"),
    IssuerRecord("R-41234567", "Arcadia Computing Ltd.", "BIS CRS", "IS 13252 (Part 1) : 2010", "31/12/2027"),
]


def normalise_number(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


_SUFFIXES = r"\b(private limited|pvt ltd|pvt|limited|ltd|llp|inc|co)\b"


def normalise_company(value: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", (value or "").lower())
    text = re.sub(_SUFFIXES, " ", re.sub(r"\s+", " ", text))
    return re.sub(r"\s+", " ", text).strip()


class MockIssuerRegistry:
    source_name = SOURCE_NAME

    def __init__(self, records: list[IssuerRecord] | None = None) -> None:
        self._records = list(records if records is not None else _RECORDS)

    def by_number(self, number: str) -> IssuerRecord | None:
        key = normalise_number(number)
        return next((r for r in self._records if normalise_number(r.certificate_number) == key), None)

    def by_holder(self, holder: str) -> IssuerRecord | None:
        key = normalise_company(holder)
        return next((r for r in self._records if normalise_company(r.holder) == key), None)
