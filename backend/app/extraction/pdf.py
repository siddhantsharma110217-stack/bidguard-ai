"""Page-by-page PDF text extraction with PyMuPDF."""

import re
from dataclasses import dataclass

import pymupdf

# A page with fewer letters/digits than this is treated as having no
# extractable text (a scanned image, or a blank page). OCR is out of scope.
MIN_TEXT_CHARS = 10

NO_TEXT_LABEL = "No extractable text — OCR not available"


class InvalidPdf(ValueError):
    pass


@dataclass
class PdfText:
    page_count: int
    pages: list[str]  # index 0 = page 1

    @property
    def pages_without_text(self) -> list[int]:
        return [i + 1 for i, text in enumerate(self.pages) if not has_text(text)]


def has_text(text: str) -> bool:
    return len(re.findall(r"[A-Za-z0-9]", text or "")) >= MIN_TEXT_CHARS


# Words whose vertical centres are this close (in points) share a line.
LINE_TOLERANCE = 3.0


def page_text(page) -> str:
    """The page's text as visual lines, left to right, top to bottom.

    PyMuPDF's plain text output puts each table cell on its own line, which
    separates a label ("Processor") from its value. Rebuilding rows from word
    positions keeps them on one line, which is what the patterns and the
    citation check work on.
    """
    words = page.get_text("words")
    if not words:
        return ""
    words.sort(key=lambda w: ((w[1] + w[3]) / 2, w[0]))
    lines: list[list] = []
    current_y = None
    for w in words:
        y = (w[1] + w[3]) / 2
        if current_y is None or abs(y - current_y) > LINE_TOLERANCE:
            lines.append([])
            current_y = y
        lines[-1].append(w)
    return "\n".join(" ".join(w[4] for w in sorted(line, key=lambda w: w[0])) for line in lines)


def read_pdf(data: bytes) -> PdfText:
    """Extract text from every page. Raises InvalidPdf for unreadable files."""
    if not data.startswith(b"%PDF-"):
        raise InvalidPdf("the file is not a PDF (missing %PDF header)")
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types
        raise InvalidPdf(f"the PDF could not be opened ({exc})") from exc
    try:
        if doc.needs_pass:
            raise InvalidPdf("the PDF is password-protected")
        if doc.page_count == 0:
            raise InvalidPdf("the PDF has no pages")
        pages = [page_text(page) for page in doc]
        return PdfText(page_count=doc.page_count, pages=pages)
    finally:
        doc.close()
