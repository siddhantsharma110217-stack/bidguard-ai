"""Deterministic sample tender + four bidder packages for the demo.

SAMPLE DATA ONLY. Every company, person, address, phone number, email and
bank account in this module is fictional and exists solely to exercise the
demo. Any resemblance to a real entity is coincidental.

Everything here is fixed data — loading the demo twice produces byte-identical
requirements, documents and (therefore) evaluation results.

Each bidder package is deliberately constructed so the evaluator is visibly
doing real work and the bidders differ from one another:

  TechNova Systems      7 PASS · 1 REVIEW (ambiguous BIS certificate)
                        · 1 FAIL (delivery 45 > 30) · 1 MISSING (no OEM MAF)
                        -> 76.0 compliance, risk 53 HIGH, NON-RESPONSIVE
  Apex Infotech         8 PASS · 1 REVIEW · 1 FAIL (delivery 40 > 30)
                        -> 86.0 compliance, risk 33 MEDIUM, NON-RESPONSIVE
  Bharat Digital        9 PASS · 1 REVIEW
                        -> 96.0 compliance, risk 8 LOW, RESPONSIVE
  Crestline Computers   9 PASS · 1 MISSING (desirable energy rating)
                        -> 90.0 compliance, risk 20 LOW, RESPONSIVE

Every bidder's Commercial Bid also carries contact fields (`CONTACT_FIELDS`).
Apex Infotech and Crestline Computers declare the SAME phone number and bank
account while presenting as unrelated firms — a common indicator of bid
rigging / cover bidding that a reviewing officer should be able to spot.
BIS registration (REQ-007) is also checked against the fictional issuer
registry (app.verification.registry): TechNova VERIFIED (its REVIEW, from an
unreadable validity date, is unchanged), Bharat UNVERIFIED (no record) and
Apex VERIFICATION_FAILED (number differs from the issuer record) both turn
their rule PASS into REVIEW, Crestline VERIFIED.

The Red Flags page (`app.redflags`) surfaces exactly these two shared details;
TechNova and Bharat Digital share nothing and must stay unflagged.

TechNova (45 days) and Apex (40 days) both FAIL the same delivery rule
(REQ-008). Overriding only one of them produces an inconsistent-treatment flag.
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
        # The one requirement checked against the issuer's record
        # (app.verification). Every other requirement defaults to False.
        "verification_required": True,
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
# Bidder contact details. These are extracted from each bidder's Commercial
# Bid like any other field; no requirement rule reads them, so they never
# affect a compliance verdict. Keys map to the label shown to the officer.
# ---------------------------------------------------------------------------

CONTACT_FIELDS = {
    "bidder_email": "Email",
    "bidder_phone": "Phone",
    "bidder_address": "Registered Address",
    "bank_account": "Bank Account",
}

# SAMPLE DATA: fictional contact details, deliberately shared by Apex
# Infotech and Crestline Computers so the Red Flags page has a real
# collusion indicator to show (see module docstring). Do not reuse them
# for any other bidder: TechNova and Bharat Digital must stay clean.
_SHARED_PHONE = "+91 98110 36524"
_SHARED_BANK_ACCOUNT = "State Bank of India, A/c No. 39104458821, IFSC SBIN0011235"


def _contact(email: str, phone: str, address: str, bank_account: str, *, page: int) -> dict:
    """Contact block as extracted from a Commercial Bid's bidder-details page."""
    return {
        "bidder_email": {
            "value": email,
            "page": page,
            "confidence": 0.98,
            "snippet": f"E-mail: {email}",
        },
        "bidder_phone": {
            "value": phone,
            "page": page,
            "confidence": 0.97,
            "snippet": f"Contact No.: {phone}",
        },
        "bidder_address": {
            "value": address,
            "page": page,
            "confidence": 0.95,
            "snippet": f"Registered Office: {address}",
        },
        "bank_account": {
            "value": bank_account,
            "page": page,
            "confidence": 0.96,
            "snippet": f"Bank details for EMD refund / payment: {bank_account}",
        },
    }


# ---------------------------------------------------------------------------
# Bidder 1 — TechNova Systems Pvt. Ltd.  (7 PASS · 1 REVIEW · 1 FAIL · 1 MISSING)
# ---------------------------------------------------------------------------

TECHNOVA_DOCUMENTS = [
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
            **_contact(
                email="tenders@technovasystems.in",
                phone="+91 80 4718 2290",
                address="No. 14, 2nd Floor, Outer Ring Road, Marathahalli, Bengaluru, Karnataka 560037",
                bank_account="HDFC Bank, A/c No. 50200047712093, IFSC HDFC0000523",
                page=1,
            ),
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
                "value": "R-41190527",
                "page": 1,
                "confidence": 0.42,
                "ambiguous": True,
                "ambiguity_reason": (
                    "the uploaded scan is low-resolution and the validity date is not "
                    "readable, so the certificate's validity cannot be confirmed"
                ),
                "snippet": "BIS Registration No. R-41190527  |  Valid upto: ____/____  (illegible)",
            },
            "certificate_holder": {
                "value": "TechNova Systems Pvt. Ltd.",
                "page": 1,
                "confidence": 0.95,
                "snippet": "Registered to: TechNova Systems Pvt. Ltd.",
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Bidder 2 — Apex Infotech Solutions  (9 PASS · 1 FAIL: delivery 40 > 30)
# Shares its phone number and bank account with Crestline Computers.
# ---------------------------------------------------------------------------

APEX_DOCUMENTS = [
    {
        "original_filename": "Technical_Bid.pdf",
        "doc_type": "TECHNICAL_BID",
        "doc_type_confidence": 0.96,
        "classified_by": "SIGNATURE",
        "page_count": 5,
        "has_text_layer": True,
        "fields": {
            "processor": {
                "value": "Intel Core i5-1335U",
                "page": 2,
                "confidence": 0.97,
                "snippet": "CPU: Intel Core i5-1335U (13th Gen, 10 cores, up to 4.6 GHz)",
            },
            "ram_gb": {
                "value": "16 GB DDR4",
                "numeric": 16,
                "page": 2,
                "confidence": 0.97,
                "snippet": "RAM: 16 GB DDR4 3200 MHz (2 x 8 GB)",
            },
            "storage_gb": {
                "value": "512 GB SSD",
                "numeric": 512,
                "page": 2,
                "confidence": 0.96,
                "snippet": "Storage: 512 GB M.2 PCIe SSD",
            },
            "display_inch": {
                "value": "14 inch FHD anti-glare",
                "numeric": 14,
                "page": 2,
                "confidence": 0.96,
                "snippet": "Screen: 14.0\" FHD (1920 x 1080) anti-glare, 300 nits",
            },
            "operating_system": {
                "value": "Windows 11 Professional (OEM)",
                "page": 3,
                "confidence": 0.98,
                "snippet": "OS: Genuine Windows 11 Professional, factory pre-installed with OEM licence",
            },
            "energy_rating": {
                "value": "BEE 4-star rated",
                "page": 4,
                "confidence": 0.90,
                "snippet": "Energy: BEE 4-star rated (certificate enclosed)",
            },
        },
    },
    {
        "original_filename": "Warranty_Certificate.pdf",
        "doc_type": "WARRANTY_CERTIFICATE",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "warranty_years": {
                "value": "3 years onsite OEM warranty",
                "numeric": 3,
                "page": 1,
                "confidence": 0.96,
                "snippet": "The OEM provides 3 (three) years onsite comprehensive warranty on all quoted units.",
            },
        },
    },
    {
        "original_filename": "Commercial_Bid.pdf",
        "doc_type": "COMMERCIAL_BID",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 3,
        "has_text_layer": True,
        "fields": {
            "delivery_days": {
                "value": "40 days from PO",
                "numeric": 40,
                "page": 2,
                "confidence": 0.96,
                "snippet": "Delivery Period: Supply shall be completed within 40 (forty) days of receipt of Purchase Order.",
            },
            **_contact(
                email="bids@apexinfotech.co.in",
                phone=_SHARED_PHONE,
                address="B-42, Sector 63, Noida, Uttar Pradesh 201301",
                bank_account=_SHARED_BANK_ACCOUNT,
                page=1,
            ),
        },
    },
    {
        "original_filename": "BIS_Certificate.pdf",
        "doc_type": "BIS_CERTIFICATE",
        "doc_type_confidence": 0.93,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "bis_registration_no": {
                "value": "R-41087632",
                "page": 1,
                "confidence": 0.95,
                "snippet": "BIS Registration No. R-41087632  |  Valid upto: 31/03/2028",
            },
            "certificate_holder": {
                "value": "Apex Infotech Solutions",
                "page": 1,
                "confidence": 0.95,
                "snippet": "Registered to: Apex Infotech Solutions",
            },
        },
    },
    {
        "original_filename": "OEM_Authorization_Form.pdf",
        "doc_type": "OEM_AUTHORIZATION",
        "doc_type_confidence": 0.94,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "oem_authorization_ref": {
                "value": "MAF/2026/GEM-4471902/0187",
                "page": 1,
                "confidence": 0.94,
                "snippet": "Manufacturer Authorization Form Ref. MAF/2026/GEM-4471902/0187 issued for Bid No. GEM/2026/B/4471902.",
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Bidder 3 — Bharat Digital Technologies Pvt. Ltd.  (10 PASS)
# ---------------------------------------------------------------------------

BHARAT_DOCUMENTS = [
    {
        "original_filename": "Technical_Bid.pdf",
        "doc_type": "TECHNICAL_BID",
        "doc_type_confidence": 0.98,
        "classified_by": "SIGNATURE",
        "page_count": 7,
        "has_text_layer": True,
        "fields": {
            "processor": {
                "value": "Intel Core i7-1355U",
                "page": 2,
                "confidence": 0.97,
                "snippet": "Processor: Intel Core i7-1355U (13th Gen, 10 cores, up to 5.0 GHz)",
            },
            "ram_gb": {
                "value": "16 GB DDR5",
                "numeric": 16,
                "page": 2,
                "confidence": 0.98,
                "snippet": "Memory: 16 GB DDR5 5200 MHz, dual channel",
            },
            "storage_gb": {
                "value": "1 TB NVMe SSD",
                "numeric": 1024,
                "page": 2,
                "confidence": 0.97,
                "snippet": "Storage: 1 TB PCIe Gen4 NVMe SSD",
            },
            "display_inch": {
                "value": "14 inch FHD+ anti-glare",
                "numeric": 14,
                "page": 3,
                "confidence": 0.96,
                "snippet": "Display: 14\" FHD+ (1920 x 1200) IPS anti-glare, 400 nits",
            },
            "operating_system": {
                "value": "Windows 11 Pro (OEM licence)",
                "page": 3,
                "confidence": 0.99,
                "snippet": "Operating System: Windows 11 Pro, pre-installed, OEM licence key embedded in BIOS",
            },
            "energy_rating": {
                "value": "ENERGY STAR 8.0 certified",
                "page": 6,
                "confidence": 0.93,
                "snippet": "Certifications: ENERGY STAR 8.0, EPEAT Gold, RoHS",
            },
        },
    },
    {
        "original_filename": "Warranty_Certificate.pdf",
        "doc_type": "WARRANTY_CERTIFICATE",
        "doc_type_confidence": 0.96,
        "classified_by": "SIGNATURE",
        "page_count": 2,
        "has_text_layer": True,
        "fields": {
            "warranty_years": {
                "value": "5 years comprehensive onsite",
                "numeric": 5,
                "page": 1,
                "confidence": 0.97,
                "snippet": "Warranty: 5 (five) years comprehensive onsite, next-business-day service, parts and labour included.",
            },
        },
    },
    {
        "original_filename": "Commercial_Bid.pdf",
        "doc_type": "COMMERCIAL_BID",
        "doc_type_confidence": 0.97,
        "classified_by": "SIGNATURE",
        "page_count": 3,
        "has_text_layer": True,
        "fields": {
            "delivery_days": {
                "value": "21 days from PO",
                "numeric": 21,
                "page": 2,
                "confidence": 0.97,
                "snippet": "Delivery: All 250 units shall be delivered within 21 days from the date of Purchase Order.",
            },
            **_contact(
                email="procurement@bharatdigital.in",
                phone="+91 22 6619 4400",
                address="Unit 7, Andheri Industrial Estate, Andheri (East), Mumbai, Maharashtra 400093",
                bank_account="ICICI Bank, A/c No. 000405117386, IFSC ICIC0000004",
                page=1,
            ),
        },
    },
    {
        "original_filename": "BIS_Certificate.pdf",
        "doc_type": "BIS_CERTIFICATE",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "bis_registration_no": {
                "value": "R-41052219",
                "page": 1,
                "confidence": 0.96,
                "snippet": "BIS Registration No. R-41052219  |  Valid upto: 30/09/2027",
            },
            "certificate_holder": {
                "value": "Bharat Digital Technologies Pvt. Ltd.",
                "page": 1,
                "confidence": 0.95,
                "snippet": "Registered to: Bharat Digital Technologies Pvt. Ltd.",
            },
        },
    },
    {
        "original_filename": "OEM_Authorization_Form.pdf",
        "doc_type": "OEM_AUTHORIZATION",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "oem_authorization_ref": {
                "value": "MAF/2026/GEM-4471902/0142",
                "page": 1,
                "confidence": 0.95,
                "snippet": "Manufacturer Authorization Form Ref. MAF/2026/GEM-4471902/0142 issued for Bid No. GEM/2026/B/4471902.",
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Bidder 4 — Crestline Computers LLP  (9 PASS · 1 MISSING: desirable energy rating)
# Shares its phone number and bank account with Apex Infotech.
# ---------------------------------------------------------------------------

CRESTLINE_DOCUMENTS = [
    {
        "original_filename": "Technical_Bid.pdf",
        "doc_type": "TECHNICAL_BID",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 4,
        "has_text_layer": True,
        "fields": {
            "processor": {
                "value": "AMD Ryzen 5 7530U",
                "page": 2,
                "confidence": 0.96,
                "snippet": "Processor: AMD Ryzen 5 7530U (6 cores, up to 4.5 GHz)",
            },
            "ram_gb": {
                "value": "16 GB DDR4",
                "numeric": 16,
                "page": 2,
                "confidence": 0.97,
                "snippet": "Memory: 16 GB DDR4 3200 MHz onboard",
            },
            "storage_gb": {
                "value": "512 GB NVMe SSD",
                "numeric": 512,
                "page": 2,
                "confidence": 0.96,
                "snippet": "Storage: 512 GB NVMe M.2 SSD",
            },
            "display_inch": {
                "value": "15.6 inch FHD anti-glare",
                "numeric": 15.6,
                "page": 2,
                "confidence": 0.95,
                "snippet": "Display: 15.6\" FHD anti-glare LED backlit",
            },
            "operating_system": {
                "value": "Windows 11 Pro (OEM licence)",
                "page": 3,
                "confidence": 0.98,
                "snippet": "Operating System: Windows 11 Pro 64-bit with OEM licence",
            },
        },
    },
    {
        "original_filename": "Warranty_Certificate.pdf",
        "doc_type": "WARRANTY_CERTIFICATE",
        "doc_type_confidence": 0.94,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "warranty_years": {
                "value": "3 years onsite",
                "numeric": 3,
                "page": 1,
                "confidence": 0.96,
                "snippet": "Warranty: 3 years onsite comprehensive warranty from the OEM.",
            },
        },
    },
    {
        "original_filename": "Commercial_Bid.pdf",
        "doc_type": "COMMERCIAL_BID",
        "doc_type_confidence": 0.95,
        "classified_by": "SIGNATURE",
        "page_count": 2,
        "has_text_layer": True,
        "fields": {
            "delivery_days": {
                "value": "28 days from PO",
                "numeric": 28,
                "page": 2,
                "confidence": 0.96,
                "snippet": "Delivery: Within 28 days from the date of Purchase Order.",
            },
            **_contact(
                email="sales@crestlinecomputers.in",
                phone=_SHARED_PHONE,
                address="Plot 118, Phase II, Okhla Industrial Area, New Delhi, Delhi 110020",
                bank_account=_SHARED_BANK_ACCOUNT,
                page=1,
            ),
        },
    },
    {
        "original_filename": "BIS_Certificate.pdf",
        "doc_type": "BIS_CERTIFICATE",
        "doc_type_confidence": 0.94,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "bis_registration_no": {
                "value": "R-41093340",
                "page": 1,
                "confidence": 0.95,
                "snippet": "BIS Registration No. R-41093340  |  Valid upto: 15/01/2028",
            },
            "certificate_holder": {
                "value": "Crestline Computers LLP",
                "page": 1,
                "confidence": 0.95,
                "snippet": "Registered to: Crestline Computers LLP",
            },
        },
    },
    {
        "original_filename": "OEM_Authorization_Form.pdf",
        "doc_type": "OEM_AUTHORIZATION",
        "doc_type_confidence": 0.93,
        "classified_by": "SIGNATURE",
        "page_count": 1,
        "has_text_layer": True,
        "fields": {
            "oem_authorization_ref": {
                "value": "MAF/2026/GEM-4471902/0203",
                "page": 1,
                "confidence": 0.93,
                "snippet": "Manufacturer Authorization Form Ref. MAF/2026/GEM-4471902/0203 issued for Bid No. GEM/2026/B/4471902.",
            },
        },
    },
]

# ---------------------------------------------------------------------------
# All bidders, in load order. The first is the "primary" demo bid returned by
# `/api/demo/load` as `bid` and by `/api/dashboard` as `demo_bid_id`.
# ---------------------------------------------------------------------------

BIDDERS = [
    {"bidder_name": "TechNova Systems Pvt. Ltd.", "documents": TECHNOVA_DOCUMENTS},
    {"bidder_name": "Apex Infotech Solutions", "documents": APEX_DOCUMENTS},
    {"bidder_name": "Bharat Digital Technologies Pvt. Ltd.", "documents": BHARAT_DOCUMENTS},
    {"bidder_name": "Crestline Computers LLP", "documents": CRESTLINE_DOCUMENTS},
]

# Backwards-compatible aliases for the primary bidder.
BIDDER_NAME = BIDDERS[0]["bidder_name"]
DOCUMENTS = BIDDERS[0]["documents"]
