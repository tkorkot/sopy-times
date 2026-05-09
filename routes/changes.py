from flask import Blueprint, jsonify, request
from services import change_service, ai_service, document_service

changes_bp = Blueprint("changes", __name__)


@changes_bp.get("/")
def list_changes():
    return jsonify(change_service.get_all_changes())


@changes_bp.post("/")
def create_change():
    """
    POST /api/changes
    Body: { "document_id": int, "new_content": str, "description": str }
    Saves the change, runs AI propagation, returns change + proposals.
    """
    data = request.get_json()
    doc = document_service.get_document(data["document_id"])
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    change = change_service.record_change(
        doc_id=data["document_id"],
        original_content=doc["content"],
        new_content=data["new_content"],
        description=data.get("description", ""),
    )
    return jsonify(change), 201


@changes_bp.post("/<int:change_id>/apply")
def apply_change(change_id):
    """Apply the primary change to its document."""
    change = change_service.apply_change(change_id)
    if not change:
        return jsonify({"error": "Not found"}), 404
    return jsonify(change)


@changes_bp.post("/proposals/<int:proposal_id>/apply")
def apply_proposal(proposal_id):
    proposal = change_service.apply_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Not found"}), 404
    return jsonify(proposal)


@changes_bp.post("/proposals/<int:proposal_id>/reject")
def reject_proposal(proposal_id):
    proposal = change_service.reject_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Not found"}), 404
    return jsonify(proposal)


@changes_bp.post("/suggest-edit")
def suggest_edit():
    """
    POST /api/changes/suggest-edit
    Body: { "document_id": int, "edit_description": str }
    Returns AI-generated updated content (does NOT save — user reviews first).
    """
    data = request.get_json()
    doc = document_service.get_document(data["document_id"])
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    suggested = ai_service.generate_edit_suggestions(doc, data["edit_description"])
    return jsonify({"suggested_content": suggested})
