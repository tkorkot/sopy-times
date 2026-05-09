"""
PDF ingestion service.

extract_from_pdf(path) → dict with:
  - title, raw_text, metadata (header fields), sections (named SOP sections)

Sections are parsed by looking for the numbered headings common in lab SOPs
(1 Introduction, 2 Safety, 3 User Qualifications…, 4 Procedure, 5 Appendix).
The structured sections dict is what gets stored as `structured_content` JSON
so the AI always receives clean, labelled input rather than raw page text.
"""

import json
import re
import fitz  # PyMuPDF


# Heading patterns → canonical section key
_SECTION_PATTERNS = [
    (r"^\s*1[\s.]+Introduction",                       "introduction"),
    (r"^\s*2[\s.]+Safety",                             "safety"),
    (r"^\s*3[\s.]+User Qualifications?",               "qualifications"),
    (r"^\s*4[\s.]+Procedure",                          "procedure"),
    (r"^\s*5[\s.]+Appendix",                           "appendix"),
]


def extract_from_pdf(path: str) -> dict:
    """
    Open a PDF and return a structured dict ready for the database.

    Returns:
        {
            "title":    str,
            "raw_text": str,          # full concatenated page text
            "metadata": {             # header fields parsed from page 1
                "coral_name", "location", "category",
                "contact", "last_revision", "sop_version", "author"
            },
            "sections": {             # named SOP sections (may be empty if not found)
                "introduction", "safety", "qualifications", "procedure", "appendix"
            },
            "process_area": str,      # derived from Category or section text
            "tags":         list[str],
        }
    """
    doc = fitz.open(path)
    pages = [page.get_text() for page in doc]
    raw_text = "\n".join(pages)

    first_page = pages[0] if pages else ""
    title      = _parse_title(first_page)
    metadata   = _parse_metadata(first_page)
    sections   = _parse_sections(raw_text)
    tags       = _derive_tags(metadata, sections)

    return {
        "title":        title,
        "raw_text":     raw_text,
        "metadata":     metadata,
        "sections":     sections,
        "process_area": metadata.get("category") or "",
        "tags":         tags,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _parse_title(first_page: str) -> str:
    """First non-empty line of the first page is typically the SOP title."""
    for line in first_page.splitlines():
        stripped = line.strip()
        if stripped and "standard operating" not in stripped.lower():
            return stripped
    return "Untitled SOP"


def _parse_metadata(text: str) -> dict:
    """Extract header key–value pairs from page 1 using regex."""
    meta = {k: None for k in
            ("coral_name", "location", "category", "contact",
             "last_revision", "sop_version", "author")}

    patterns = {
        "last_revision": r"Last\s+revision[:\s]+(\d{1,2}/\d{1,2}/\d{4})",
        "sop_version":   r"Version[:\s]+(\S+)",
        "coral_name":    r"CORAL\s+Name[:\s]+(.+)",
        "location":      r"Location[:\s]+(.+)",
        "category":      r"Category[:\s]+(.+)",
        "contact":       r"Contact[:\s]+(.+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            meta[key] = m.group(1).strip()

    # Author is usually in parentheses on the first page
    m = re.search(r"\(([A-Z][a-z]+ [A-Z][a-z]+)\)", text)
    if m:
        meta["author"] = m.group(1)

    return meta


def _parse_sections(text: str) -> dict:
    """
    Walk the full document line by line and group content under section headings.
    Unrecognised text before the first heading is placed in 'preamble'.
    """
    sections: dict[str, list[str]] = {"preamble": []}
    current = "preamble"

    for line in text.splitlines():
        matched_section = None
        for pattern, key in _SECTION_PATTERNS:
            if re.match(pattern, line, re.IGNORECASE):
                matched_section = key
                break

        if matched_section:
            sections.setdefault(matched_section, [])
            current = matched_section
        else:
            sections.setdefault(current, []).append(line)

    # Collapse lists → strings, strip leading/trailing blank lines
    return {k: "\n".join(v).strip() for k, v in sections.items() if v}


def _derive_tags(metadata: dict, sections: dict) -> list[str]:
    """
    Build a short tag list from category and procedure keywords.
    Good for the search relevance prompt.
    """
    tags: list[str] = []

    category = metadata.get("category") or ""
    for word in re.split(r"[\s/,]+", category):
        word = word.strip().lower()
        if len(word) > 2:
            tags.append(word)

    procedure = sections.get("procedure", "")
    keywords = re.findall(r"\b(PPE|HF|acid|plasma|etch|clean|solder|reflow|ESD|N2|Ar|O2|wafer|substrate)\b",
                          procedure, re.IGNORECASE)
    tags += [k.lower() for k in keywords[:8]]

    return list(dict.fromkeys(tags))  # deduplicate, preserve order


def sections_to_markdown(sections: dict) -> str:
    """
    Re-assemble parsed sections into a clean markdown document.
    Used as the stored `content` field so the editor shows readable text.
    """
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
        if key in sections and sections[key]:
            heading = headings.get(key, f"## {key.title()}")
            parts.append(f"{heading}\n\n{sections[key]}" if heading else sections[key])
    return "\n\n---\n\n".join(parts)
