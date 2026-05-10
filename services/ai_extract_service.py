"""
PDF extraction via Gemini 2.0 Flash (OpenRouter).

Sends the raw PDF bytes directly to the model — no text pre-extraction needed.
The model sees the full layout, tables, and images in their original form.

Returns the same structured dict as before so callers don't change:
  {
    "title":        str,
    "metadata":     { coral_name, location, category, contact,
                      last_revision, sop_version, author },
    "sections":     { introduction, safety, qualifications,
                      procedure, appendix, preamble },
    "process_area": str,
    "tags":         [str],
  }
Returns None on failure so extract_from_pdf() can handle it.
"""

import json
import re
import base64
from openai import OpenAI
from config import Config

_client = None
MODEL = "google/gemini-2.0-flash-001"

_PROMPT = """\
You are extracting content from a semiconductor fabrication lab SOP (Standard Operating Procedure) PDF.

Return a single JSON object with this exact structure:
{
  "title":        "the process/equipment name — NOT 'Standard Operating Procedure'",
  "metadata": {
    "coral_name":    "CORAL or NEMO tool name if present",
    "location":      "bay or room if present",
    "category":      "tool category e.g. Deposition",
    "contact":       "contact person(s)",
    "last_revision": "date string",
    "sop_version":   "version string",
    "author":        "author name(s)"
  },
  "sections": {
    "introduction":   "Introduction section content (markdown)",
    "safety":         "Safety section content (markdown)",
    "qualifications": "User Qualifications and Responsibilities section (markdown)",
    "procedure":      "Operating Procedures section (markdown)",
    "appendix":       "Appendix section content (markdown)",
    "preamble":       "any content before section 1"
  },
  "process_area": "e.g. Etch or Deposition",
  "tags": ["5-15 lowercase keywords"]
}

Rules:
- Skip the Table of Contents entirely — do not include dot-leader lines
- Preserve ALL tables as markdown pipe tables with | separators
- Preserve original step numbering exactly as written (4.1, 4.1.1, etc.)
- Format Notes/Warnings/Cautions as: > ⚠️ Note: text
- Use "" for missing sections or metadata fields
- Preserve all parameter values, temperatures, pressures, times character-for-character
- Return ONLY the JSON object, no markdown fences, no commentary
"""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
    return _client


def ai_extract_sop(pdf_path: str, filename: str = "") -> dict | None:
    """Send PDF directly to Gemini and return structured SOP dict, or None on failure."""
    if not getattr(Config, "OPENROUTER_API_KEY", None):
        return None

    try:
        with open(pdf_path, "rb") as f:
            pdf_b64 = base64.standard_b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[ai_extract] Could not read PDF {pdf_path}: {e}")
        return None

    try:
        response = _get_client().chat.completions.create(
            model=MODEL,
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {
                        "type": "file",
                        "file": {
                            "filename": filename or "document.pdf",
                            "file_data": f"data:application/pdf;base64,{pdf_b64}",
                        },
                    },
                ],
            }],
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        return _normalise(json.loads(raw))

    except Exception as e:
        print(f"[ai_extract] Gemini extraction failed: {e}")
        return None


def _normalise(data: dict) -> dict:
    meta_keys    = ("coral_name", "location", "category", "contact",
                    "last_revision", "sop_version", "author")
    section_keys = ("introduction", "safety", "qualifications",
                    "procedure", "appendix", "preamble")

    meta     = data.get("metadata") or {}
    sections = data.get("sections") or {}

    return {
        "title":        str(data.get("title") or "Untitled SOP").strip(),
        "metadata":     {k: (meta.get(k) or None) for k in meta_keys},
        "sections":     {k: str(sections.get(k) or "").strip() for k in section_keys},
        "process_area": str(data.get("process_area") or "").strip(),
        "tags":         [str(t).lower() for t in (data.get("tags") or [])],
    }
