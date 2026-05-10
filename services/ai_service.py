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
MODEL = "google/gemini-2.5-flash"

def _parse_json_response(raw: str, fallback):
    """
    Safely parse JSON returned by an LLM.

    Handles:
    - empty responses
    - ```json ... ``` markdown fences
    - extra text before/after the JSON
    """
    import re

    if not raw:
        return fallback

    raw = raw.strip()

    # Remove markdown fences if model returns ```json ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # First try normal JSON parsing
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to extract the first JSON array or object from the response
    try:
        array_start = raw.find("[")
        array_end = raw.rfind("]")

        object_start = raw.find("{")
        object_end = raw.rfind("}")

        if array_start != -1 and array_end != -1 and array_end > array_start:
            return json.loads(raw[array_start:array_end + 1])

        if object_start != -1 and object_end != -1 and object_end > object_start:
            return json.loads(raw[object_start:object_end + 1])

    except json.JSONDecodeError:
        pass

    print("Could not parse AI JSON response:")
    print(repr(raw))

    return fallback

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=Config.OPENROUTER_API_KEY,
        )
    return _client


def _chat(prompt: str, max_tokens: int = 5000) -> str:
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
        sorted descending by relevance_score.
    """
    if not documents:
        return []

    doc_summaries = "\n".join(
        f"[ID {d['id']}] {d['title']} | Area: {d['process_area']} | Tags: {', '.join(d['tags'])}"
        for d in documents
    )

    p = user_profile
    persona_lines = []

    if p.get("current_role"):
        persona_lines.append(f"Role: {p['current_role']}")
    if p.get("experience_level"):
        persona_lines.append(f"Experience: {p['experience_level']}")
    if p.get("education"):
        persona_lines.append(f"Education: {p['education']}")
    if p.get("field_of_study"):
        persona_lines.append(f"Field of study: {p['field_of_study']}")
    if p.get("certifications"):
        persona_lines.append(f"Certifications: {', '.join(p['certifications'])}")
    if p.get("process_areas"):
        persona_lines.append(f"Process areas: {', '.join(p['process_areas'])}")
    if p.get("tool_names"):
        persona_lines.append(f"Tools: {p['tool_names']}")

    persona_block = "\n".join(persona_lines) if persona_lines else "No profile provided"

    prompt = f"""You are an expert semiconductor process engineer helping someone find the most relevant SOPs for their background.

User persona:
{persona_block}

Available SOPs:
{doc_summaries}

Return a valid JSON array.

Each element must have exactly these fields:
  "id": document id as an integer
  "relevance_score": float from 0.0 to 1.0
  "reason": one sentence explaining why this SOP is relevant

Rules:
- Order from most to least relevant.
- Only include documents with relevance_score > 0.2.
- Return ONLY valid JSON.
- Do not use markdown fences.
- Do not include explanations outside the JSON.

Example:
[
  {{
    "id": 1,
    "relevance_score": 0.85,
    "reason": "This SOP is relevant because it matches the user's process area and experience level."
  }}
]
"""

    raw = _chat(prompt)
    ranked = _parse_json_response(raw, fallback=[])

    if not isinstance(ranked, list):
        return []

    id_to_doc = {d["id"]: d for d in documents}
    results = []

    for item in ranked:
        if not isinstance(item, dict):
            continue

        doc_id = item.get("id")
        if doc_id not in id_to_doc:
            continue

        try:
            score = float(item.get("relevance_score", 0))
        except (TypeError, ValueError):
            score = 0.0

        reason = item.get("reason", "")
        if not isinstance(reason, str):
            reason = str(reason)

        if score > 0.2:
            results.append(
                {
                    "document": id_to_doc[doc_id],
                    "relevance_score": score,
                    "reason": reason,
                }
            )

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    return results[:6] # Return maximum the top 6 results


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

    import re as _re
    raw = raw.strip()
    raw = _re.sub(r"^```(?:json)?\s*", "", raw)
    raw = _re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except Exception:
        return []


def generate_edit_suggestions(document: dict, edit_description: str) -> dict:
    """
    Given a document and a plain-English description of the desired edit,
    return a dict with:
      "original_snippet"  — the exact text in the document that should change
                            (empty string "" for pure additions)
      "replacement"       — the replacement text (or the new content being added)
      "full_content"      — the full updated document content
      "summary"           — one-sentence description of what changed
      "edit_type"         — "replace" | "add" | "delete"
    """
    content = document["content"][:8000]

    prompt = f"""You are an expert manufacturing process engineer helping to update an SOP.

DOCUMENT: {document['title']}
CURRENT CONTENT:
{content}

REQUESTED CHANGE:
{edit_description}

Determine the edit type first:
- "replace" — existing text is being changed or reworded
- "add"     — new content is being inserted or appended (nothing removed)
- "delete"  — content is being removed

Return a JSON object with these fields:
  "edit_type":        "replace", "add", or "delete"
  "original_snippet": for "replace"/"delete" — the exact verbatim text from the document that changes
                      (copy character-for-character; keep it short — just the changed part)
                      for "add" — empty string ""
  "replacement":      for "replace" — the new text replacing original_snippet
                      for "add"     — the full new content being added (e.g. the new section)
                      for "delete"  — empty string ""
  "full_content":     the complete updated document content with the change applied
  "summary":          one sentence describing what was changed and why

Examples:
- "add a questions section at the end" → edit_type="add", original_snippet="", replacement="## Questions\\n\\n1. ...", full_content=<full doc + new section>
- "change 200W to 180W" → edit_type="replace", original_snippet="200W", replacement="180W", full_content=<full doc with 200W→180W>
- "remove the appendix" → edit_type="delete", original_snippet=<appendix text>, replacement="", full_content=<full doc without appendix>

Return ONLY the JSON object, no markdown fences."""

    raw = _chat(prompt, max_tokens=4096)

    # Strip any accidental markdown fences
    import re as _re
    raw = _re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = _re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except Exception:
        # Fallback: treat response as full content rewrite
        return {
            "original_snippet": "",
            "replacement":      "",
            "full_content":     raw,
            "summary":          edit_description,
        }


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

def generate_personalized_process_page(
    process: dict,
    user_profile: dict,
    documents: list[dict],
) -> dict:
    """
    Generate personalized process page content using:
    - selected process step
    - user persona
    - matching SOP/database documents

    Returns:
      process_summary
      tool_summary
      learning_focus
      parameters
      recommended_sops
    """

    def join_list(value):
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return value or ""

    def get_years_text(experience_level: str) -> str:
        """
        Convert your dropdown experience labels into approximate readable years.
        This does not need to be perfect; it is just for prompt personalization.
        """
        if not experience_level:
            return "unknown"

        exp = experience_level.lower()

        if "none" in exp:
            return "0"
        if "less than 6" in exp:
            return "less than 0.5"
        if "6–12" in exp or "6-12" in exp:
            return "0.5 to 1"
        if "1–2" in exp or "1-2" in exp:
            return "1 to 2"
        if "3–5" in exp or "3-5" in exp:
            return "3 to 5"
        if "6–10" in exp or "6-10" in exp:
            return "6 to 10"
        if "10+" in exp:
            return "10+"

        return experience_level

    learner_background = user_profile.get("field_of_study") or user_profile.get("education") or "general technical"
    years_experience = get_years_text(user_profile.get("experience_level", ""))
    previous_processes = join_list(user_profile.get("process_areas", [])) or "no prior process areas listed"
    previous_tools = user_profile.get("tool_names", "") or "no prior tools listed"
    current_role = user_profile.get("current_role", "") or "learner"
    target_role = user_profile.get("target_role", "") or "not specified"
    learning_goal = user_profile.get("learning_goal", "") or "understand the process"
    certifications = join_list(user_profile.get("certifications", [])) or "no listed certifications"

    doc_lines = []
    for d in documents[:8]:
        doc_lines.append(
            f"""[DOC {d.get("id")}]
Title: {d.get("title", "")}
Document type: {d.get("doc_type", "")}
Step: {d.get("step_name", "")}
Step type: {d.get("step_type_name", "")}
Process area: {d.get("process_area", "")}
Tags: {join_list(d.get("tags", []))}
Content excerpt:
{(d.get("content") or "")[:1600]}
"""
        )

    docs_block = "\n\n".join(doc_lines) if doc_lines else "No matching SOP documents found."

    prompt = f"""
You are creating a personalized semiconductor process page for SOP Hub.

The selected process is:
PROCESS NAME: {process.get("short_name", "")}
FULL PROCESS TITLE: {process.get("title", "")}
PROCESS AREA: {process.get("process_area", "")}

User persona:
- Current role: {current_role}
- Background: {learner_background}
- Years of semiconductor experience: {years_experience}
- Previously worked on these semiconductor processes: {previous_processes}
- Previously worked with these tools: {previous_tools}
- Certifications/training: {certifications}
- Target role: {target_role}
- Main learning goal: {learning_goal}

Relevant SOP/document context from our database:
{docs_block}

Write content for a personalized process page.

PROCESS OVERVIEW INSTRUCTIONS:
Please write a short summary about {process.get("short_name", "")} during semiconductor fabrication.
Tune it for someone with a {learner_background} background with {years_experience} years of experience in semiconductors.
They have worked on {previous_processes} semiconductor processes previously.

With higher years of experience, provide more nuance about the role of this process in developing a chip than just baseline understanding.

The process summary should have this structure:
1. 1–2 sentences: overview of the process and its role in creating a semiconductor.
2. 1 sentence: importance of the step and its connection to nearby/upstream/downstream fabrication processes.
3. Short bullet-style phrasing about types or variations of the process.
4. A short example of what is done in this process, tuned to the user's {learner_background} background.

If the user has less experience or no experience, include a brief note about what they might find interesting based on their current field/background.

TOOL OVERVIEW INSTRUCTIONS:
For the {process.get("short_name", "")} semiconductor fabrication process, provide a concise overview of how a representative machine works.
Use a machine from MIT.nano as the baseline when possible, but do not invent exact model details if the SOP context does not provide them.
Provide:
1. 1 sentence overview of how the tool works.
2. 1 sentence about a unique feature or thing to watch out for.
3. 1 sentence about what someone with a {learner_background} background might find particularly interesting.
The user has {years_experience} years of experience and has previously worked with {previous_tools} tools.
If the user has more experience, provide more detail on how the machine works and other similar processes/tools.

PARAMETER TABLE INSTRUCTIONS:
Provide a table where:
- column 1 is parameter
- column 2 is purpose
- column 3 is range of values or options that should be specified for the process

For example, for sputter:
parameter = Material
options = Pt, Ti, Ag, Au, etc.

IMPORTANT SAFETY/CONFIDENTIALITY RULES:
- Do not invent confidential recipe settings.
- Do not provide exact proprietary values.
- Use generic safe ranges/options like "tool/process dependent" when exact SOP values are unavailable.
- Base recommended SOPs only on the provided document list.
- Keep the writing concise and suitable for a web page.

Return ONLY valid JSON with this exact structure:

{{
  "process_summary": "HTML-free text. Can include short paragraphs and bullet-style lines using plain text.",
  "tool_summary": "HTML-free text. 1 short paragraph.",
  "learning_focus": [
    "specific thing this user should focus on",
    "specific thing this user should focus on",
    "specific thing this user should focus on"
  ],
  "parameters": [
    {{
      "parameter": "Parameter name",
      "purpose": "Why this parameter matters",
      "example_value": "Generic range/options/value"
    }}
  ],
  "recommended_sops": [
    {{
      "id": 1,
      "title": "Document title",
      "reason": "Why this SOP is useful for this user"
    }}
  ]
}}

Return at most 6 parameters.
Return at most 5 recommended_sops.
Return ONLY JSON. No markdown fences.
"""

    raw = _chat(prompt, max_tokens=3000)
    parsed = _parse_json_response(raw, fallback=None)

    if not isinstance(parsed, dict):
        return {
            "process_summary": (
                f"{process.get('title', 'This process')} is part of the semiconductor fabrication flow. "
                "It affects wafer quality, repeatability, and downstream processing."
            ),
            "tool_summary": (
                "The tools used in this area control important process conditions. "
                "Understanding those conditions helps connect SOP steps to real wafer outcomes."
            ),
            "learning_focus": [
                "Understand what this process changes on the wafer.",
                "Learn which parameters are safety-critical and quality-critical.",
                "Connect this process to upstream and downstream steps.",
            ],
            "parameters": [
                {
                    "parameter": "Main process condition",
                    "purpose": "Controls the result of the process.",
                    "example_value": "Tool/process dependent",
                }
            ],
            "recommended_sops": [
                {
                    "id": d.get("id"),
                    "title": d.get("title"),
                    "reason": "This SOP is related to the selected process area.",
                }
                for d in documents[:5]
            ],
        }

    parsed.setdefault("process_summary", "")
    parsed.setdefault("tool_summary", "")
    parsed.setdefault("learning_focus", [])
    parsed.setdefault("parameters", [])
    parsed.setdefault("recommended_sops", [])

    return parsed