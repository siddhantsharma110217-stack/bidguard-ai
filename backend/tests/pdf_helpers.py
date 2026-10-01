"""Build small PDFs inside tests (fpdf2 + Pillow, no files on disk)."""

import io
from datetime import datetime, timezone

from fpdf import FPDF
from PIL import Image, ImageDraw

from app.seed import sample_data


def scan_image() -> bytes:
    """An image with writing drawn as pixels: no text layer at all."""
    img = Image.new("L", (600, 800), color=245)
    draw = ImageDraw.Draw(img)
    draw.text((60, 100), "BIS Registration No. R-41234567", fill=20)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_pdf(pages: list) -> bytes:
    """One PDF page per item: a list of text lines, or None for a scanned
    (image-only) page. A ("row", label, value) tuple renders a table row."""
    pdf = FPDF(format="A4")
    pdf.set_creation_date(datetime(2026, 1, 1, tzinfo=timezone.utc))
    for lines in pages:
        pdf.add_page()
        if lines is None:
            pdf.image(io.BytesIO(scan_image()), x=15, y=15, w=180)
            continue
        for line in lines:
            if isinstance(line, tuple):
                _, label, value = line
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(50, 8, label, border=1)
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 8, value, border=1, new_x="LMARGIN", new_y="NEXT")
            else:
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


COMPLIANT_PAGES = [
    ["Covering letter", "Bid for Supply of Laptop Computers, Bid No. GEM/2026/B/4471902"],
    [
        "Technical compliance",
        ("row", "Processor", "Intel Core i5-1335U"),
        ("row", "Memory (RAM)", "16 GB DDR4"),
        ("row", "Storage", "512 GB NVMe SSD"),
        ("row", "Display", "14 inch FHD anti-glare"),
        ("row", "Operating System", "Windows 11 Pro"),
        ("row", "Warranty", "3 years comprehensive onsite"),
        ("row", "Energy Efficiency", "ENERGY STAR 8.0 certified"),
    ],
    ["Commercial terms", "Delivery Schedule: Complete delivery within 25 days of Purchase Order."],
    ["BIS Registration No.: R-41234567"],
    ["MAF Ref. No.: MAF/2026/TEST/0001"],
]


class Req:
    """Stand-in for a Requirement row, built from the demo tender spec."""

    def __init__(self, spec: dict, rid: int):
        self.id = rid
        self.code = spec["code"]
        self.title = spec["title"]
        self.description = spec["description"]
        self.category = spec["category"]
        self.obligation = spec["obligation"]
        self.rule_type = spec["rule_type"]
        self.rule_params = spec["rule_params"]
        self.source_page = spec["source_page"]


def demo_requirements() -> list[Req]:
    return [Req(s, i) for i, s in enumerate(sample_data.REQUIREMENTS, start=1)]
