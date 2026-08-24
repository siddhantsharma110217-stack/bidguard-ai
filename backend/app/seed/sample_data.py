"""Deterministic sample tender + bidder package for the demo.

Everything here is fixed data — loading the demo twice produces byte-identical
requirements, documents and (therefore) evaluation results.

The bidder package is deliberately constructed to yield a MIXED result so the
evaluator is visibly doing real work:
    7 PASS · 1 REVIEW (ambiguous BIS certificate) · 1 FAIL (delivery 45 > 30)
    · 1 MISSING (no OEM authorisation document)
"""

TENDER = {
    "title": "Supply of Laptop Computers for Government Office",
    "reference_no": "GEM/2026/B/4471902",
    "filename": "GeM_Bid_4471902_Laptops.pdf",
    "status": "READY",
    "page_count": 12,
    "meta": {
        "buyer": "Directorate of Administrative Reforms",
        "quantity": 250,
        "bid_type": "GeM Custom Bid",
    },
}

# ---------------------------------------------------------------------------
# Requirements — 10, spanning TECHNICAL / COMPLIANCE / DELIVERY categories.
# `rule_params.field` is the key the evaluator looks up in document fields.
# ---------------------------------------------------------------------------

REQUIREMENTS = [
    {
        "code": "REQ-001",
        "category": "TECHNICAL",
        "title": "Processor",
        "description": "Intel Core i5 (11th generation or later) or equivalent/better processor.",
        "obligation": "MANDATORY",
        "rule_type": "tier_min",
        "rule_params": {
            "field": "processor",
            "minimum": "i5",
            "expected_display": "Intel Core i5 or higher",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 5,
        "source_page": 4,
        "source_clause": "Clause 3.1 (a) — The offered laptop shall be fitted with an Intel Core i5 processor of 11th generation or later, or an equivalent or superior processor.",
    },
    {
        "code": "REQ-002",
        "category": "TECHNICAL",
        "title": "System Memory (RAM)",
        "description": "Minimum 16 GB DDR4/DDR5 system memory.",
        "obligation": "MANDATORY",
        "rule_type": "numeric_min",
        "rule_params": {
            "field": "ram_gb",
            "threshold": 16,
            "unit": "GB",
            "expected_display": "Minimum 16 GB",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 5,
        "source_page": 4,
        "source_clause": "Clause 3.1 (b) — Minimum 16 GB DDR4 or DDR5 RAM shall be provided.",
    },
    {
        "code": "REQ-003",
        "category": "TECHNICAL",
        "title": "Storage",
        "description": "Minimum 512 GB Solid State Drive (SSD).",
        "obligation": "MANDATORY",
        "rule_type": "numeric_min",
        "rule_params": {
            "field": "storage_gb",
            "threshold": 512,
            "unit": "GB",
            "expected_display": "Minimum 512 GB SSD",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 4,
        "source_page": 4,
        "source_clause": "Clause 3.1 (c) — Storage shall be a minimum of 512 GB SSD (NVMe preferred).",
    },
    {
        "code": "REQ-004",
        "category": "TECHNICAL",
        "title": "Display Size",
        "description": "Minimum 14 inch anti-glare display.",
        "obligation": "MANDATORY",
        "rule_type": "numeric_min",
        "rule_params": {
            "field": "display_inch",
            "threshold": 14,
            "unit": "inch",
            "expected_display": "Minimum 14 inch",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 3,
        "source_page": 5,
        "source_clause": "Clause 3.1 (d) — Display shall not be smaller than 14 inches, anti-glare finish.",
    },
    {
        "code": "REQ-005",
        "category": "TECHNICAL",
        "title": "Operating System",
        "description": "Pre-loaded Windows 11 Professional with valid OEM licence.",
        "obligation": "MANDATORY",
        "rule_type": "text_contains_any",
        "rule_params": {
            "field": "operating_system",
            "options": ["Windows 11 Pro", "Windows 11 Professional"],
            "expected_display": "Windows 11 Professional",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 4,
        "source_page": 5,
        "source_clause": "Clause 3.2 — Each unit shall be supplied with pre-loaded Windows 11 Professional and a valid OEM licence.",
    },
    {
        "code": "REQ-006",
        "category": "COMPLIANCE",
        "title": "Onsite Warranty",
        "description": "Minimum 3 years comprehensive onsite OEM warranty.",
        "obligation": "MANDATORY",
        "rule_type": "numeric_min",
        "rule_params": {
            "field": "warranty_years",
            "threshold": 3,
            "unit": "years",
            "expected_display": "Minimum 3 years onsite",
        },
        "expected_doc_types": ["WARRANTY_CERTIFICATE", "TECHNICAL_BID"],
        "weight": 5,
        "source_page": 6,
        "source_clause": "Clause 4.1 — A minimum of three (3) years comprehensive onsite warranty from the OEM is mandatory.",
    },
    {
        "code": "REQ-007",
        "category": "COMPLIANCE",
        "title": "BIS Certification",
        "description": "Valid BIS registration under the Compulsory Registration Scheme.",
        "obligation": "MANDATORY",
        "rule_type": "presence",
        "rule_params": {
            "field": "bis_registration_no",
            "expected_display": "Valid BIS registration certificate",
        },
        "expected_doc_types": ["BIS_CERTIFICATE"],
        "weight": 5,
        "source_page": 7,
        "source_clause": "Clause 5.2 — The offered model shall carry valid BIS registration under the Compulsory Registration Scheme (CRS). A copy of the certificate shall be enclosed.",
    },
    {
        "code": "REQ-008",
        "category": "DELIVERY",
        "title": "Delivery Period",
        "description": "Complete delivery within 30 days of Purchase Order.",
        "obligation": "MANDATORY",
        "rule_type": "numeric_max",
        "rule_params": {
            "field": "delivery_days",
            "threshold": 30,
            "unit": "days",
            "expected_display": "Within 30 days of PO",
        },
        "expected_doc_types": ["COMMERCIAL_BID"],
        "weight": 4,
        "source_page": 8,
        "source_clause": "Clause 6.1 — Delivery shall be completed within thirty (30) days from the date of issue of the Purchase Order.",
    },
    {
        "code": "REQ-009",
        "category": "COMPLIANCE",
        "title": "OEM Authorization",
        "description": "Manufacturer Authorization Form (MAF) from the OEM.",
        "obligation": "MANDATORY",
        "rule_type": "presence",
        "rule_params": {
            "field": "oem_authorization_ref",
            "expected_display": "Valid OEM Manufacturer Authorization Form",
        },
        "expected_doc_types": ["OEM_AUTHORIZATION"],
        "weight": 5,
        "source_page": 8,
        "source_clause": "Clause 5.4 — Bidders who are not the OEM shall submit a Manufacturer Authorization Form (MAF) issued specifically for this tender.",
    },
    {
        "code": "REQ-010",
        "category": "COMPLIANCE",
        "title": "Energy Efficiency",
        "description": "ENERGY STAR certified or BEE star-rated equipment.",
        "obligation": "DESIRABLE",
        "rule_type": "text_contains_any",
        "rule_params": {
            "field": "energy_rating",
            "options": ["ENERGY STAR", "BEE"],
            "expected_display": "ENERGY STAR / BEE rated",
        },
        "expected_doc_types": ["TECHNICAL_BID"],
        "weight": 2,
        "source_page": 9,
        "source_clause": "Clause 7.3 — Preference shall be given to ENERGY STAR certified or BEE star-rated equipment.",
    },
]

# ---------------------------------------------------------------------------
# Bidder package — TechNova Systems Pvt. Ltd.
# ---------------------------------------------------------------------------

BIDDER_NAME = "TechNova Systems Pvt. Ltd."

DOCUMENTS = [
    {
        "original_filename": "Technical_Bid.pdf",
        "doc_type": "TECHNICAL_BID",
        "doc_type_confidence": 0.97,
        "classified_by": "SIGNATURE",
        "page_count": 6,
        "has_text_layer": True,
        "fields": {
            "processor": {
                "value": "Intel Core i5-13420H",
                "page": 2,
                "confidence": 0.96,
                "snippet": "Processor: Intel Core i5-13420H (13th Gen, 8 cores, up to 4.6 GHz)",
            },
            "ram_gb": {
                "value": "16 GB DDR5",
                "numeric": 16,
                "page": 2,
                "confidence": 0.98,
                "snippet": "Memory: 16 GB DDR5 4800 MHz (1 x 16 GB SODIMM, upgradable to 32 GB)",
            },
            "storage_gb": {
                "value": "512 GB NVMe SSD",
                "numeric": 512,
                "page": 2,
                "confidence": 0.97,
                "snippet": "Storage: 512 GB PCIe NVMe M.2 Solid State Drive",
            },
            "display_inch": {
                "value": "15.6 inch FHD anti-glare",
                "numeric": 15.6,
                "page": 3,
                "confidence": 0.95,
                "snippet": "Display: 15.6\" FHD (1920 x 1080) IPS, anti-glare, 250 nits",
            },
            "operating_system": {
                "value": "Windows 11 Pro (OEM licence)",
                "page": 3,
                "confidence": 0.99,
                "snippet": "Operating System: Windows 11 Pro 64-bit, pre-loaded with OEM licence",
            },
            "energy_rating": {
                "value": "ENERGY STAR 8.0 certified",
                "page": 5,
                "confidence": 0.91,
                "snippet": "Compliance: ENERGY STAR 8.0 certified; RoHS compliant",
            },
        },
    },
    {
        "original_filename": "Warranty_Certificate.pdf",
        "doc_type": "WARRANTY_CERTIFICATE",
        "doc_type_confidence": 0.94,
        "classified_by": "SIGNATURE",
        "page_count": 2,
        "has_text_layer": True,
        "fields": {
            "warranty_years": {
                "value": "3 years comprehensive onsite",
                "numeric": 3,
                "page": 1,
                "confidence": 0.97,
                "snippet": "We hereby confirm 3 (three) years comprehensive onsite warranty covering parts and labour from the date of installation.",
            },
        },
    },
    {
        "original_filename": "Commercial_Bid.pdf",
        "doc_type": "COMMERCIAL_BID",
        "doc_type_confidence": 0.96,
        "classified_by": "SIGNATURE",
        "page_count": 3,
        "has_text_layer": True,
        "fields": {
            "delivery_days": {
                "value": "45 days from PO",
                "numeric": 45,
                "page": 2,
                "confidence": 0.95,
                "snippet": "Delivery Schedule: Complete delivery within 45 days from the date of Purchase Order.",
            },
        },
    },
    {
        "original_filename": "BIS_Certificate_Scan.pdf",
        "doc_type": "BIS_CERTIFICATE",
        "doc_type_confidence": 0.71,
        "classified_by": "SIGNATURE+AI",
        "page_count": 1,
        "has_text_layer": False,
        "fields": {
            "bis_registration_no": {
                "value": "R-4119____ (partially legible)",
                "page": 1,
                "confidence": 0.42,
                "ambiguous": True,
                "ambiguity_reason": (
                    "the uploaded scan is low-resolution, the registration number is only "
                    "partially legible and the validity date is not readable"
                ),
                "snippet": "BIS Registration No. R-4119____  |  Valid upto: ____/____  (illegible)",
            },
        },
    },
]
