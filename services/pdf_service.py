"""
PDF extraction service.

extract_from_pdf(path) returns a dict with:
  - title         : detected from largest-font text on page 1
  - raw_text      : full text (tables replaced with markdown tables)
  - metadata      : header fields (CORAL/NEMO Name, Location, Category, Contact,
                    Last revision, Version, Author)
  - sections      : named SOP sections keyed by introduction / safety /
                    qualifications / procedure / appendix / preamble
  - process_area  : from Category header field
  - tags          : derived from category + procedure keywords
  - image_count   : number of embedded images found (not extracted to disk)
"""

import re
import fitz  # PyMuPDF


# Patterns tried in order; first match wins.
# Handles  "1 Introduction", "1. Introduction", "1.0 Introduction"
# as well as plain un-numbered headings on their own line.
_SECTION_PATTERNS = [
    (r"^\s*1[\s.]+Introduction",             "introduction"),
    (r"^\s*2[\s.]+Safety",                   "safety"),
    (r"^\s*3[\s.]+User\s+Qualifications?",   "qualifications"),
    (r"^\s*4[\s.]+Procedure",                "procedure"),
    (r"^\s*5[\s.]+Appendix",                 "appendix"),
    # Un-numbered standalone headings
    (r"^Introduction\s*$",                   "introduction"),
    (r"^Safety(\s+Precautions?)?\s*$",       "safety"),
    (r"^User\s+Qualifications?\s*$",         "qualifications"),
    (r"^Procedure\s*$",                      "procedure"),
    (r"^Appendix\s*$",                       "appendix"),
]

_BOILERPLATE = {
    "standard operating procedure", "user standard operating procedure",
    "sop", "user sop", "nemo", "coral", "rev", "revision",
}


# ── Public API ────────────────────────────────────────────────────────────────

def extract_from_pdf(path: str) -> dict:
    doc = fitz.open(path)

    first_page_text = doc[0].get_text() if doc else ""

    # Build full text page by page; tables become markdown inside the text
    page_texts = [_extract_page_text(page) for page in doc]
    raw_text   = "\n\n".join(page_texts)

    title    = _parse_title(doc)
    metadata = _parse_metadata(first_page_text)
    sections = _parse_sections(raw_text)
    tags     = _derive_tags(metadata, sections)

    image_count = sum(len(page.get_images()) for page in doc)

    return {
        "title":        title,
        "raw_text":     raw_text,
        "metadata":     metadata,
        "sections":     sections,
        "process_area": metadata.get("category") or "",
        "tags":         tags,
        "image_count":  image_count,
    }


def sections_to_markdown(sections: dict) -> str:
    """Re-assemble parsed sections into a readable markdown document."""
    order = ["introduction", "safety", "qualifications", "procedure", "appendix", "preamble"]
    headings = {
        "introduction":   "## 1  Introduction",
        "safety":         "## 2  Safety",
        "qualifications": "## 3  User Qualifications and Responsibilities",
        "procedure":      "## 4  Procedure",
        "appendix":       "## 5  Appendix",
        "preamble":       "",
    }
    parts = []
    for key in order:
        body = sections.get(key, "")
        if not body:
            continue
        heading = headings.get(key, f"## {key.title()}")
        parts.append(f"{heading}\n\n{body}" if heading else body)
    return "\n\n---\n\n".join(parts)


# ── Page-level extraction ─────────────────────────────────────────────────────

def _extract_page_text(page: fitz.Page) -> str:
    """
    Return page text with any tables replaced by markdown table blocks.
    Text blocks that fall inside a table's bounding box are dropped so the
    content is not duplicated.
    """
    table_map: list[tuple[tuple, str]] = []  # (bbox, markdown)
    try:
        tf = page.find_tables()
        for table in tf.tables:
            rows = table.extract()
            if rows and any(any(c for c in row) for row in rows):
                table_map.append((table.bbox, _rows_to_markdown(rows)))
    except Exception:
        pass

    if not table_map:
        return page.get_text()

    # Walk text blocks; skip blocks inside a table bbox, insert table once
    parts: list[str] = []
    inserted: set[int] = set()

    for block in page.get_text("blocks"):
        bx0, by0, bx1, by1, text = block[:5]
        in_table = False
        for i, (tbbox, md) in enumerate(table_map):
            tx0, ty0, tx1, ty1 = tbbox
            if bx0 >= tx0 - 2 and by0 >= ty0 - 2 and bx1 <= tx1 + 2 and by1 <= ty1 + 2:
                in_table = True
                if i not in inserted:
                    parts.append(md)
                    inserted.add(i)
                break
        if not in_table:
            t = text.strip()
            if t:
                parts.append(t)

    # Tables not yet inserted (no matching text block above them)
    for i, (_, md) in enumerate(table_map):
        if i not in inserted:
            parts.append(md)

    return "\n".join(parts)


def _rows_to_markdown(rows: list[list]) -> str:
    """Convert extracted table rows to a markdown table string."""
    if not rows:
        return ""

    def cell(c) -> str:
        return str(c).replace("\n", " ").strip() if c is not None else ""

    header = rows[0]
    sep    = ["---"] * len(header)
    lines  = [
        "| " + " | ".join(cell(c) for c in header) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows[1:]:
        # Pad row if shorter than header
        padded = list(row) + [None] * max(0, len(header) - len(row))
        lines.append("| " + " | ".join(cell(c) for c in padded) + " |")
    return "\n".join(lines)


# ── Metadata & section parsing ────────────────────────────────────────────────

def _parse_title(doc: fitz.Document) -> str:
    """
    Detect title as the span with the largest font size on page 1 that isn't
    a boilerplate phrase.  Falls back to the first non-empty, non-boilerplate
    line of raw text.
    """
    page = doc[0]
    try:
        best_size, best_text = 0.0, ""
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"].strip()
                    size = span.get("size", 0.0)
                    if (size > best_size
                            and len(text) > 3
                            and text.lower() not in _BOILERPLATE):
                        best_size, best_text = size, text
        if best_text:
            return best_text
    except Exception:
        pass

    for line in page.get_text().splitlines():
        t = line.strip()
        if t and t.lower() not in _BOILERPLATE:
            return t
    return "Untitled SOP"


def _parse_metadata(text: str) -> dict:
    """Extract header key-value pairs from page-1 text."""
    meta = {k: None for k in
            ("coral_name", "location", "category", "contact",
             "last_revision", "sop_version", "author")}

    patterns = {
        # NEMO is used in some labs as the reservation system instead of CORAL
        "coral_name":    r"(?:CORAL|NEMO)\s+Name[:\s]+(.+?)(?:\n|$)",
        "location":      r"Location[:\s]+(.+?)(?:\n|$)",
        "category":      r"Category[:\s]+(.+?)(?:\n|$)",
        "contact":       r"Contact[:\s]+(.+?)(?:\n|$)",
        "last_revision": r"Last\s+[Rr]evision[:\s]+(\d{1,2}/\d{1,2}/\d{2,4})",
        "sop_version":   r"Version[:\s]+(\S+)",
    }
    for key, pat in patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            meta[key] = m.group(1).strip()

    # Author often appears as "(Firstname Lastname)" on the title page
    m = re.search(r"\(([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\)", text)
    if m:
        meta["author"] = m.group(1)

    return meta


def _parse_sections(text: str) -> dict:
    """
    Walk the document line by line and group content under SOP section keys.
    Content before the first recognised heading goes into 'preamble'.
    """
    sections: dict[str, list[str]] = {"preamble": []}
    current = "preamble"

    for line in text.splitlines():
        matched = None
        stripped = line.strip()
        for pattern, key in _SECTION_PATTERNS:
            if re.match(pattern, stripped, re.IGNORECASE):
                matched = key
                break
        if matched:
            sections.setdefault(matched, [])
            current = matched
        else:
            sections.setdefault(current, []).append(line)

    return {k: "\n".join(v).strip() for k, v in sections.items() if "".join(v).strip()}


def _derive_tags(metadata: dict, sections: dict) -> list[str]:
    tags: list[str] = []

    for word in re.split(r"[\s/,]+", metadata.get("category") or ""):
        w = word.strip().lower()
        if len(w) > 2:
            tags.append(w)

    searchable = " ".join(sections.get(k, "") for k in ("procedure", "safety", "introduction"))
    keywords = re.findall(
        r"\b(PPE|HF|acid|plasma|etch|clean|solder|reflow|ESD|N2|Ar|O2|"
        r"wafer|substrate|ALD|CVD|PVD|RIE|DRIE|sputter|evapor|anneal|"
        r"oxidat|lithograph|resist|develop|photolithograph|CMP|polish)\b",
        searchable, re.IGNORECASE,
    )
    tags += [k.lower() for k in keywords[:12]]

    return list(dict.fromkeys(tags))  # deduplicate, preserve order
