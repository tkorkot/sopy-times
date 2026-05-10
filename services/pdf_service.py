"""
PDF extraction service — delegates to Gemini via ai_extract_service.

extract_from_pdf(path, filename) returns:
  { title, raw_text, metadata, sections, process_area, tags }

sections_to_markdown(sections) reassembles sections into a readable markdown doc.
"""

import os
from services.ai_extract_service import ai_extract_sop

os.environ.setdefault("MUPDF_QUIET", "1")


def extract_from_pdf(path: str, filename: str = "") -> dict:
    """Extract structured content from a PDF using Gemini."""
    fname = filename or os.path.basename(path)
    result = ai_extract_sop(str(path), fname)

    if not result:
        return {"title": fname, "raw_text": "", "metadata": {},
                "sections": {}, "process_area": "", "tags": []}

    raw_text = sections_to_markdown(result["sections"])
    return {
        "title":        result["title"],
        "raw_text":     raw_text,
        "metadata":     result["metadata"],
        "sections":     result["sections"],
        "process_area": result["process_area"],
        "tags":         result["tags"],
    }


def sections_to_markdown(sections: dict) -> str:
    """Turn any sections dict into markdown — keys become ## headings.
    'preamble' is the one exception: it has no heading (it's pre-title content)."""
    parts = []
    for key, body in sections.items():
        body = (body or "").strip()
        if not body:
            continue
        if key == "preamble":
            parts.append(body)
        else:
            heading = key.replace("_", " ").title()
            parts.append(f"## {heading}\n\n{body}")
    return "\n\n---\n\n".join(parts)
