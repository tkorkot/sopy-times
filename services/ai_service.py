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

    prompt = f"""You are an expert manufacturing process engineer helping a new employee find relevant SOPs.

User profile:
- Job title: {user_profile.get('job_title')}
- Experience level: {user_profile.get('experience_level')}
- Area of interest: {user_profile.get('area_of_interest')}

Available SOPs:
{doc_summaries}

Return a JSON array where each element has:
  "id": <document id as integer>,
  "relevance_score": <float 0.0 to 1.0>,
  "reason": <one sentence why this SOP is relevant to the user>

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
