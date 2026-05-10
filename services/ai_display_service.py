"""
AI display formatting service.

Reformats stored SOP content into clean markdown that mirrors the standard
lab SOP structure as closely as possible to the original PDF layout:
  1. Introduction
  2. Safety
  3. User Qualifications and Responsibilities
  4. Operating Procedures
  5. Appendix

Result is cached in the browser session (sessionStorage) so the API is
called only once per document per browser session.
"""

import json
import re
from config import Config

_MAX_CHARS = 10_000

# Mirrors the structure in ai_extract_service.SOP_SECTIONS
_SECTION_HEADINGS = [
    ("introduction",   "## 1  Introduction"),
    ("safety",         "## 2  Safety"),
    ("qualifications", "## 3  User Qualifications and Responsibilities"),
    ("procedure",      "## 4  Operating Procedures"),
    ("appendix",       "## 5  Appendix"),
]


def format_sop_content(content: str, title: str = "", structured_content: str = "") -> str:
    """
    Use the LLM to reformat raw SOP content into clean, well-structured markdown.
    Falls back to lightly cleaned raw content if the API is unavailable.
    """
    if not getattr(Config, "OPENROUTER_API_KEY", None):
        return _basic_clean(content)

    # Build source from structured sections if available — richer than flat content
    source = content
    if structured_content:
        try:
            sections = json.loads(structured_content)
            parts = []
            for key, heading in _SECTION_HEADINGS:
                body = sections.get(key, "").strip()
                if body:
                    parts.append(f"{heading}\n\n{body}")
            preamble = sections.get("preamble", "").strip()
            if preamble and not parts:
                parts.append(preamble)
            if parts:
                source = "\n\n---\n\n".join(parts)
        except Exception:
            pass

    source = source[:_MAX_CHARS]

    section_guide = "\n".join(
        f"  {heading}: content from the {key} section"
        for key, heading in _SECTION_HEADINGS
    )

    prompt = f"""You are formatting a semiconductor lab SOP titled "{title}" for clean on-screen reading.

The text below was extracted from a PDF. Reformat it into clean markdown that mirrors the standard SOP layout:

{section_guide}

Formatting rules:
- Use the exact headings above (## 1  Introduction, ## 2  Safety, etc.)
- Introduction: 2-4 sentences describing what the process does and why
- Safety: bullet list with ⚠️ prefix for each hazard; sub-bullets for PPE and emergency steps
- User Qualifications and Responsibilities: bullet list of who can operate and what training is required
- Operating Procedures — CRITICAL:
    • Preserve the ORIGINAL step numbering exactly (4.1, 4.1.1, 4.2 etc.)
    • Main steps as top-level numbered list items; sub-steps indented beneath them
    • ANY table in the procedure must stay as a markdown table — never convert to prose
    • If pipe characters (|) appear in the source, those are markdown tables — keep them intact
    • Notes/Warnings/Cautions → "> ⚠️ Note: text" blockquotes
    • Never paraphrase parameter values, equipment names, temperatures, times, or settings
- Appendix: keep ALL reference tables as markdown tables; do not summarise them
- Remove all page headers, footers, "Page X of Y", and repeated boilerplate lines
- Do NOT invent or change any technical content — only reformat
- Omit sections that have no content
- Return ONLY the formatted markdown, no fences or commentary

RAW CONTENT:
{source}"""

    try:
        from openai import OpenAI
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
        response = client.chat.completions.create(
            model="google/gemini-2.5-flash",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        result = response.choices[0].message.content.strip()
        result = re.sub(r"^```(?:markdown)?\s*", "", result)
        result = re.sub(r"\s*```$", "", result)
        return result
    except Exception as e:
        print(f"[ai_display_service] formatting failed: {e}")
        return _basic_clean(content)


def _basic_clean(content: str) -> str:
    """Minimal cleanup when AI is unavailable: collapse excessive blank lines."""
    lines = content.splitlines()
    result, blanks = [], 0
    for line in lines:
        if line.strip() == "":
            blanks += 1
            if blanks <= 1:
                result.append("")
        else:
            blanks = 0
            result.append(line)
    return "\n".join(result)
