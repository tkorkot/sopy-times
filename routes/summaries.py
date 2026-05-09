from flask import Blueprint, jsonify, request
from services import document_service, ai_service

summaries_bp = Blueprint("summaries", __name__)


@summaries_bp.get("/roles")
def list_roles():
    """GET /api/summaries/roles — available roles with display labels."""
    return jsonify([
        {"value": "technician",          "label": "Lab Technician"},
        {"value": "process_engineer",    "label": "Process Engineer"},
        {"value": "mechanical_engineer", "label": "Mechanical Engineer"},
        {"value": "electrical_engineer", "label": "Electrical Engineer"},
        {"value": "student",             "label": "Student"},
        {"value": "new_employee",        "label": "New Employee"},
        {"value": "safety_officer",      "label": "Safety Officer"},
    ])


@summaries_bp.post("/<int:doc_id>")
def generate_summary(doc_id):
    """
    POST /api/summaries/<doc_id>
    Body: {
        "role": str,                  # e.g. "technician"
        "user_profile": dict,         # full persona from sessionStorage (optional)
        "extra_context": str          # free-text user note (optional)
    }
    Returns: { "role": str, "role_label": str, "summary": str (markdown) }
    """
    data = request.get_json()
    role = (data.get("role") or "new_employee").lower().replace(" ", "_")

    doc = document_service.get_document(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    # Merge user profile into extra_context so the AI can personalise further
    profile = data.get("user_profile") or {}
    extra_parts = []
    if data.get("extra_context"):
        extra_parts.append(data["extra_context"])
    if profile.get("current_role"):
        extra_parts.append(f"The user's current role is: {profile['current_role']}.")
    if profile.get("experience_level"):
        extra_parts.append(f"Experience level: {profile['experience_level']}.")
    if profile.get("process_areas"):
        extra_parts.append(f"They work in: {', '.join(profile['process_areas'])}.")
    if profile.get("certifications") and "None" not in profile["certifications"]:
        extra_parts.append(f"Certifications: {', '.join(profile['certifications'])}.")

    summary = ai_service.generate_role_summary(
        document=doc,
        role=role,
        extra_context=" ".join(extra_parts),
    )

    role_labels = {
        "technician": "Lab Technician", "process_engineer": "Process Engineer",
        "mechanical_engineer": "Mechanical Engineer", "electrical_engineer": "Electrical Engineer",
        "student": "Student", "new_employee": "New Employee", "safety_officer": "Safety Officer",
    }

    return jsonify({"role": role, "role_label": role_labels.get(role, role), "summary": summary})
