# services/chatbot_service.py

"""
Chatbot service for process-aware, persona-aware SOP Q&A.

This service is used when the user clicks "Ask Questions" from process.html.
It answers using:
- the selected process step
- the user's saved persona/profile
- matching SOP documents from the database
- the user's chat question
"""

import json
import re
from services.ai_service import _chat


def _join_list(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return value or ""


def _format_persona(user_profile: dict) -> str:
    return f"""
Learner name: {user_profile.get("learner_name", "")}
Current role: {user_profile.get("current_role", "")}
Experience level: {user_profile.get("experience_level", "")}
Education: {user_profile.get("education", "")}
Field of study: {user_profile.get("field_of_study", "")}
Process areas: {_join_list(user_profile.get("process_areas", []))}
Certifications/training: {_join_list(user_profile.get("certifications", []))}
Tools/platforms: {user_profile.get("tool_names", "")}
Target role: {user_profile.get("target_role", "")}
Learning goal: {user_profile.get("learning_goal", "")}
LinkedIn URL: {user_profile.get("linkedin_url", "")}
""".strip()


def _format_documents(documents: list[dict], max_docs: int = 8, max_chars_each: int = 2200) -> str:
    if not documents:
        return "No matching SOP documents were found for this process."

    blocks = []

    for d in documents[:max_docs]:
        tags = _join_list(d.get("tags", []))
        content = (d.get("content") or "")[:max_chars_each]

        blocks.append(
            f"""
[DOCUMENT {d.get("id")}]
Title: {d.get("title", "")}
Document type: {d.get("doc_type", "")}
Process area: {d.get("process_area", "")}
Step: {d.get("step_name", "")}
Step type: {d.get("step_type_name", "")}
CORAL name: {d.get("coral_name", "")}
Location: {d.get("location", "")}
Tags: {tags}

Content excerpt:
{content}
""".strip()
        )

    return "\n\n---\n\n".join(blocks)


def answer_process_chat(
    process: dict,
    user_profile: dict,
    documents: list[dict],
    message: str,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Answer a user's question from the process page.

    Args:
        process: PROCESS_META entry for selected process
        user_profile: profile saved from index.html/sessionStorage
        documents: matching SOP docs from DB
        message: user's current chat question
        chat_history: optional previous messages, [{"role": "user"|"assistant", "content": "..."}]

    Returns:
        {
          "answer": str,
          "sources": [{"id": int, "title": str}],
          "process": dict
        }
    """

    if not message or not message.strip():
        return {
            "answer": "Ask me a question about this process or one of the related SOPs.",
            "sources": [],
            "process": process,
        }

    persona_block = _format_persona(user_profile)
    docs_block = _format_documents(documents)

    history_block = ""
    if chat_history:
        safe_history = chat_history[-8:]
        history_lines = []
        for item in safe_history:
            role = item.get("role", "user")
            content = item.get("content", "")
            if content:
                history_lines.append(f"{role.upper()}: {content[:1000]}")
        history_block = "\n".join(history_lines)

    prompt = f"""You are an SOP Hub assistant for semiconductor process learning.

The user is asking a question from a process detail page.

SELECTED PROCESS:
Title: {process.get("title", "")}
Short name: {process.get("short_name", "")}
Process area: {process.get("process_area", "")}

USER PERSONA:
{persona_block}

RELATED SOP / DOCUMENT CONTEXT:
{docs_block}

RECENT CHAT HISTORY:
{history_block if history_block else "No prior chat history."}

USER QUESTION:
{message}

Instructions:
- Answer using the selected process, the user persona, and the SOP/document context.
- Personalize the explanation to the user's role, experience, education, target role, and learning goal.
- If the user is new/student, explain simply.
- If the user is an engineer/technician, be practical and process-focused.
- Do not invent exact confidential recipe settings.
- If the SOP context does not contain an exact answer, say that clearly and give a safe general explanation.
- Mention relevant SOP/document titles when helpful.
- Keep the answer concise but useful.
- Use markdown bullets only when they help readability.
"""

    try:
        answer = _chat(prompt, max_tokens=1800)
    except Exception as e:
        return {
            "answer": f"Sorry, I could not generate an answer right now. Server error: {e}",
            "sources": [],
            "process": process,
        }

    sources = []
    for d in documents[:8]:
        sources.append({
            "id": d.get("id"),
            "title": d.get("title", ""),
        })

    return {
        "answer": answer,
        "sources": sources,
        "process": process,
    }