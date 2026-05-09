"""
AI service — uses OpenRouter (OpenAI-compatible API) for four capabilities:
  1. Rank SOPs by relevance for a given user profile
  2. Suggest where a change should be propagated to other documents
  3. Generate an updated document from a plain-English edit description
  4. Generate a role-tailored study guide / summary for any SOP

Change the MODEL constant to swap between any OpenRouter-supported model,
e.g. "openai/gpt-4o", "google/gemini-2.0-flash-001", "meta-llama/llama-3.3-70b-instruct"
"""

import json
from openai import OpenAI
from config import Config

_client = None
MODEL = "openai/gpt-4o-mini"   # cheap + fast; swap to "openai/gpt-4o" for higher quality


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
    return _client


def _chat(prompt: str, max_tokens: int = 1024) -> str:
    response = _get_client().chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


def analyze_sop_relevance(user_profile: dict, documents: list[dict]) -> list[dict]:
    """
    Rank documents by relevance to the user's job title, experience level,
    and area of interest.

    Returns:
        List of {"document": <doc dict>, "relevance_score": float, "reason": str}
        sorted descending by relevance_score (score > 0.2 only).
    """
    if not documents:
        return []

    doc_summaries = "\n".join(
        f"[ID {d['id']}] {d['title']} | Area: {d['process_area']} | Tags: {', '.join(d['tags'])}"
        for d in documents
    )

    # Build a human-readable persona block from whatever fields are filled in
    p = user_profile
    persona_lines = []
    if p.get("current_role"):        persona_lines.append(f"Role: {p['current_role']}")
    if p.get("experience_level"):    persona_lines.append(f"Experience: {p['experience_level']}")
    if p.get("education"):           persona_lines.append(f"Education: {p['education']}")
    if p.get("field_of_study"):      persona_lines.append(f"Field of study: {p['field_of_study']}")
    if p.get("certifications"):      persona_lines.append(f"Certifications: {', '.join(p['certifications'])}")
    if p.get("process_areas"):       persona_lines.append(f"Process areas: {', '.join(p['process_areas'])}")
    if p.get("tool_names"):          persona_lines.append(f"Tools: {p['tool_names']}")
    persona_block = "\n".join(persona_lines) if persona_lines else "No profile provided"

    prompt = f"""You are an expert semiconductor process engineer helping someone find the most relevant SOPs for their background.

User persona:
{persona_block}

Available SOPs:
{doc_summaries}

Return a JSON array where each element has:
  "id": <document id as integer>,
  "relevance_score": <float 0.0 to 1.0>,
  "reason": <one sentence explaining why this SOP is relevant given their specific role and background>

Consider their role, experience level, and process areas when scoring.
Order from most to least relevant. Only include documents with score > 0.2.
Return ONLY the JSON array, no other text."""

    raw = _chat(prompt)
    ranked = json.loads(raw)
    id_to_doc = {d["id"]: d for d in documents}

    return [
        {
            "document": id_to_doc[item["id"]],
            "relevance_score": item["relevance_score"],
            "reason": item["reason"],
        }
        for item in ranked
        if item["id"] in id_to_doc
    ]


def suggest_change_propagation(
    changed_doc: dict,
    original_content: str,
    new_content: str,
    all_documents: list[dict],
) -> list[dict]:
    """
    After a document is edited, find other documents that may need a similar
    update and propose the specific text changes.

    Returns:
        List of ChangeProposal dicts:
        {
            "target_document_id": int,
            "original_section": str,
            "proposed_section": str,
            "reason": str,
            "confidence": float
        }
    """
    other_docs = [d for d in all_documents if d["id"] != changed_doc["id"]]
    if not other_docs:
        return []

    other_summaries = "\n\n".join(
        f"[ID {d['id']}] {d['title']}\n{d['content'][:800]}"
        for d in other_docs
    )

    prompt = f"""You are an expert manufacturing process engineer reviewing a change to an SOP.

CHANGED DOCUMENT: {changed_doc['title']}

ORIGINAL:
{original_content}

UPDATED:
{new_content}

OTHER DOCUMENTS (may need similar updates):
{other_summaries}

Identify which other documents should be updated based on this change and propose exact text edits.

Return a JSON array where each element has:
  "target_document_id": <int>,
  "original_section": <exact text in that document that should change>,
  "proposed_section": <replacement text>,
  "reason": <one sentence explaining why this change applies>,
  "confidence": <float 0.0 to 1.0>

Only include documents that genuinely need a change. If none, return an empty array [].
Return ONLY the JSON array."""

    raw = _chat(prompt, max_tokens=2048)
    return json.loads(raw)


def generate_edit_suggestions(document: dict, edit_description: str) -> str:
    """
    Given a document and a plain-English description of the desired edit,
    return the full updated document content.
    """
    prompt = f"""You are an expert manufacturing process engineer helping to update an SOP.

DOCUMENT: {document['title']}
CURRENT CONTENT:
{document['content']}

REQUESTED CHANGE:
{edit_description}

Rewrite the document incorporating the requested change. Keep all other sections intact.
Return ONLY the updated document content, no commentary."""

    return _chat(prompt, max_tokens=4096)


# ── Role-based study guide ────────────────────────────────────────────────────

_ROLE_INSTRUCTIONS = {
    "technician": """You are writing a practical cheat-sheet for a **lab technician** who will operate this equipment hands-on every day.
Focus on:
- A short plain-English summary of what the process does and why it matters
- The procedure steps distilled into a quick-reference checklist
- Critical safety rules (PPE, hazards) in plain language — no jargon
- The most common mistakes and how to avoid them
- What to do if something looks wrong (alarms, unexpected readings)
Skip deep engineering theory. Use bullet points and short sentences.""",

    "process_engineer": """You are writing a technical reference for a **process engineer** who owns and optimises this process.
Focus on:
- All process parameters, tolerances, and specifications in one place
- Quality control criteria and measurement methods
- How this step connects to upstream and downstream processes
- Which parameters can be tuned and what effect each has
- Failure modes and their root causes
Include tables where useful.""",

    "mechanical_engineer": """You are writing a summary for a **mechanical engineer** who needs to understand the equipment.
Focus on:
- Equipment description — mechanical components, how they work, what they do
- Relevant physical specs (pressures, forces, temperatures, flow rates, tolerances)
- Mechanical interlocks and safety mechanisms
- Maintenance requirements and failure modes
- Any mechanical setup or alignment steps in the procedure
Skip chemistry and electrical details unless they interact with mechanical components.""",

    "electrical_engineer": """You are writing a summary for an **electrical engineer** focused on the control and power systems.
Focus on:
- Power requirements and supply specs
- Control system overview (panel, interlocks, sensors, actuators)
- Any software or PLC interfaces
- Electrical safety requirements
- Signal flows (e.g. how the thermocouple feeds back to the controller)
Skip chemistry and materials unless they affect electrical components.""",

    "student": """You are writing a **study guide** for a student encountering this process for the first time.
Include:
- What this process is and the scientific/engineering principle behind it (explain the physics or chemistry simply)
- Why each major parameter matters (e.g. why that specific pressure or temperature)
- Key vocabulary and terms defined in plain English
- A numbered summary of what happens step by step in the procedure
- 3–5 "exam-style" questions a student should be able to answer after reading this SOP
Make it educational, not just descriptive.""",

    "new_employee": """You are writing an **onboarding guide** for someone new to this lab or company who will work near or with this process.
Include:
- A plain-English overview: what this process does and where it fits in the bigger picture
- The key safety rules they must know before setting foot near the equipment
- Who to talk to if they have questions (refer to Contact field)
- What qualifications or training they need before they can operate it
- A short glossary of the most important terms
Keep it welcoming and jargon-free.""",

    "safety_officer": """You are writing a **safety summary** for a safety officer auditing this process.
Focus exclusively on:
- All required PPE, listed clearly
- Every identified hazard and the corresponding control measure
- Emergency procedures (spill, exposure, equipment failure)
- Required training and qualifications before operation
- Things that are explicitly prohibited
- Any chemicals, voltages, or pressures that exceed standard thresholds
Format as a structured checklist where possible.""",
}


def generate_role_summary(document: dict, role: str, extra_context: str = "") -> str:
    """
    Generate a role-tailored study guide / summary for a document.

    Args:
        document:      to_dict() output from the Document model
        role:          one of the keys in _ROLE_INSTRUCTIONS, or a free-form string
        extra_context: optional user note (e.g. "I'll be working on the night shift")

    Returns:
        Markdown-formatted study guide string
    """
    instruction = _ROLE_INSTRUCTIONS.get(
        role.lower().replace(" ", "_").replace("-", "_"),
        _ROLE_INSTRUCTIONS["new_employee"],
    )

    # Build a structured context block from whatever fields are populated
    meta_lines = []
    for label, key in [("CORAL Name", "coral_name"), ("Location", "location"),
                        ("Category", "category"), ("Contact", "contact"),
                        ("Last Revision", "last_revision")]:
        val = document.get(key)
        if val:
            meta_lines.append(f"{label}: {val}")
    meta_block = "\n".join(meta_lines)

    # Prefer structured sections if available, fall back to full content
    import json as _json
    structured = document.get("structured_content")
    if structured:
        try:
            sections = _json.loads(structured)
            content_block = "\n\n".join(
                f"=== {k.upper()} ===\n{v}"
                for k, v in sections.items()
                if v and k != "preamble"
            )
        except Exception:
            content_block = document.get("content", "")
    else:
        content_block = document.get("content", "")

    prompt = f"""{instruction}

---
SOP TITLE: {document['title']}
{meta_block}

FULL CONTENT:
{content_block}
{f"USER NOTE: {extra_context}" if extra_context else ""}
---

Write the study guide now. Use markdown with clear headings and bullet points.
Do not copy the SOP verbatim — synthesise and explain it for your audience."""

    return _chat(prompt, max_tokens=2500)
