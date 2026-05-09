from flask import Blueprint, jsonify, request
from services import document_service, ai_service

search_bp = Blueprint("search", __name__)


@search_bp.post("/")
def search():
    """
    POST /api/search
    Body: { "job_title": str, "experience_level": str, "area_of_interest": str }
    Returns documents ranked by relevance for the given user profile.
    """
    user_profile = request.get_json()
    all_docs = document_service.get_all_documents()
    ranked = ai_service.analyze_sop_relevance(user_profile, all_docs)
    return jsonify(ranked)
