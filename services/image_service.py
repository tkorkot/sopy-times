"""
PDF image extraction service.

Extracts embedded images from each page, saves them to
  static/doc_images/<doc_id>/
and tags each image with the SOP section its page belongs to
(introduction / safety / qualifications / procedure / appendix)
by matching the surrounding text against the known section headings.

Small images (< 80 px in either dimension) are skipped.
"""

import os
import re
from pathlib import Path
import fitz

os.environ.setdefault("MUPDF_QUIET", "1")

IMAGES_DIR = Path("static") / "doc_images"
MIN_DIM    = 80

# Ordered so the first match wins (same priority as pdf_service._SECTION_PATTERNS)
_SECTION_SIGNALS = [
    ("procedure",      [r"operating\s+procedure", r"^\s*4[\s.]", r"^procedure\s*$"]),
    ("safety",         [r"^\s*2[\s.]", r"^safety\b", r"hazard", r"ppe\b", r"precaution"]),
    ("qualifications", [r"^\s*3[\s.]", r"qualification", r"responsibilities"]),
    ("introduction",   [r"^\s*1[\s.]", r"^introduction\s*$", r"purpose\s*:"]),
    ("appendix",       [r"^\s*5[\s.]", r"^appendix\b", r"reference\s+table"]),
]


def _detect_section(page_text: str) -> str:
    """Return the SOP section name that best describes this page's content."""
    text = page_text.lower()
    for section, patterns in _SECTION_SIGNALS:
        for pat in patterns:
            if re.search(pat, text, re.MULTILINE | re.IGNORECASE):
                return section
    return "procedure"   # most images live in the procedure section


def extract_images(pdf_path: str, doc_id: int) -> list[dict]:
    """
    Extract all meaningful images from the PDF and save to disk.

    Returns a list of dicts:
      filename, page_number, page_total,
      position_y   (0-1 within the page),
      doc_position (0-1 across the whole document),
      section_name (introduction / safety / qualifications / procedure / appendix),
      width, height
    """
    pdf = fitz.open(pdf_path)
    total_pages = len(pdf)
    out_dir = IMAGES_DIR / str(doc_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pre-compute section for each page (cheap text scan)
    page_sections = [_detect_section(page.get_text()) for page in pdf]

    results    = []
    seen_xrefs = set()

    for page_num, page in enumerate(pdf):
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                pix = fitz.Pixmap(pdf, xref)
                if pix.n > 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                if pix.width < MIN_DIM or pix.height < MIN_DIM:
                    continue

                rects = page.get_image_rects(img_info)
                rect  = rects[0] if rects else fitz.Rect(0, 0, 1, 1)
                page_h     = page.rect.height or 1
                position_y = rect.y0 / page_h
                doc_pos    = (page_num + position_y) / total_pages

                filename = f"p{page_num:02d}_x{xref}.png"
                pix.save(str(out_dir / filename))

                results.append({
                    "filename":     filename,
                    "page_number":  page_num,
                    "page_total":   total_pages,
                    "position_y":   round(position_y, 4),
                    "doc_position": round(doc_pos, 4),
                    "section_name": page_sections[page_num],
                    "width":        pix.width,
                    "height":       pix.height,
                })
            except Exception as e:
                print(f"[image_service] skipped xref {xref} on page {page_num}: {e}")

    return results


def image_url(doc_id: int, filename: str) -> str:
    return f"/static/doc_images/{doc_id}/{filename}"
