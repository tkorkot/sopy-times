from flask import Blueprint, request, jsonify
from database.db import db
from database.models import Document
from services.ai_service import generate_personalized_process_page

process_bp = Blueprint("process", __name__)


PROCESS_META = {
    "sample-prep": {
        "title": "Sample Prep / Surface Cleaning",
        "short_name": "Sample Prep",
        "process_area": "Sample Prep / Surface Cleaning",
        "process_image": "images/sample-prep-process.png",
        "tool_image": "images/sample-prep-tool.png",
    },
    "deposition": {
        "title": "Deposition / Film Formation",
        "short_name": "Deposition",
        "process_area": "Deposition / Film Formation",
        "process_image": "images/deposition-process.png",
        "tool_image": "images/deposition-tool.png",
    },
    "thermal-processing": {
        "title": "Thermal Processing",
        "short_name": "Thermal Processing",
        "process_area": "Thermal Processing",
        "process_image": "images/thermal-processing-process.png",
        "tool_image": "images/thermal-processing-tool.png",
    },
    "resist-processing": {
        "title": "Resist Processing",
        "short_name": "Resist Processing",
        "process_area": "Resist Processing",
        "process_image": "images/resist-processing-process.png",
        "tool_image": "images/resist-processing-tool.png",
    },
    "lithography": {
        "title": "Lithography / Exposure",
        "short_name": "Lithography",
        "process_area": "Lithography / Exposure",
        "process_image": "images/lithography-process.png",
        "tool_image": "images/lithography-tool.png",
    },
    "etch": {
        "title": "Etch / Pattern Transfer",
        "short_name": "Etch",
        "process_area": "Etch / Pattern Transfer",
        "process_image": "images/etch-process.png",
        "tool_image": "images/etch-tool.png",
    },
    "strip-clean": {
        "title": "Strip Resist / Clean",
        "short_name": "Strip / Clean",
        "process_area": "Strip Resist / Clean",
        "process_image": "images/strip-clean-process.png",
        "tool_image": "images/strip-clean-tool.png",
    },
    "metrology-inspection": {
        "title": "Metrology / Inspection",
        "short_name": "Metrology",
        "process_area": "Metrology / Inspection",
        "process_image": "images/metrology-inspection-process.png",
        "tool_image": "images/metrology-inspection-tool.png",
    },
    "packaging": {
        "title": "Packaging / Wirebonding",
        "short_name": "Packaging",
        "process_area": "Packaging / Wirebonding",
        "process_image": "images/packaging-process.png",
        "tool_image": "images/packaging-tool.png",
    },
}


def _doc_to_small_dict(doc):
    return {
        "id": doc.id,
        "title": getattr(doc, "title", ""),
        "process_area": getattr(doc, "process_area", ""),
        "tags": getattr(doc, "tags", []) or [],
        "content": (getattr(doc, "content", "") or "")[:2500],
        "coral_name": getattr(doc, "coral_name", ""),
        "location": getattr(doc, "location", ""),
    }


@process_bp.route("/<process_slug>/personalized", methods=["POST"])
def personalized_process_page(process_slug):
    meta = PROCESS_META.get(process_slug)

    if not meta:
        return jsonify({"error": "Unknown process"}), 404

    profile = request.get_json(silent=True) or {}

    docs = (
        db.session.query(Document)
        .filter(Document.process_area == meta["process_area"])
        .all()
    )

    doc_payload = [_doc_to_small_dict(d) for d in docs]

    generated = generate_personalized_process_page(
        process=meta,
        user_profile=profile,
        documents=doc_payload,
    )

    generated["process"] = meta
    generated["documents"] = doc_payload[:8]

    return jsonify(generated)