from flask import Blueprint, request, jsonify
from sqlalchemy import or_
from database.db import db
from database.models import Document, DocumentImage, Step, StepType
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
        "doc_type": getattr(doc, "doc_type", ""),
        "tags": getattr(doc, "tags", []) or [],
        "content": (getattr(doc, "content", "") or "")[:2500],
        "coral_name": getattr(doc, "coral_name", ""),
        "location": getattr(doc, "location", ""),
        "step_name": doc.step.name if getattr(doc, "step", None) else "",
        "step_type_name": doc.step_type.name if getattr(doc, "step_type", None) else "",
    }


def _safe_int(val):
    try:
        return int(val)
    except (TypeError, ValueError):
        return -1


@process_bp.route("/<process_slug>/personalized", methods=["POST"])
def personalized_process_page(process_slug):
    meta = PROCESS_META.get(process_slug)

    if not meta:
        return jsonify({"error": "Unknown process"}), 404

    profile = request.get_json(silent=True) or {}

    possible_names = [meta["title"], meta["short_name"], meta["process_area"]]
    short_name = meta["short_name"]

    docs = (
        db.session.query(Document)
        .outerjoin(Step, Document.step_id == Step.id)
        .outerjoin(StepType, Document.step_type_id == StepType.id)
        .filter(Document.doc_type == "SOP")
        .filter(
            or_(
                Step.name.in_(possible_names),
                StepType.name.in_(possible_names),
                Document.process_area.in_(possible_names),
                # Flexible fallback: step/area contains the process short name
                Step.name.ilike(f"%{short_name}%"),
                StepType.name.ilike(f"%{short_name}%"),
                Document.process_area.ilike(f"%{short_name}%"),
            )
        )
        .all()
    )

    doc_payload = [_doc_to_small_dict(d) for d in docs]

    print(f"[process] slug={process_slug}, short_name={short_name}, matched={len(doc_payload)}")

    generated = generate_personalized_process_page(
        process=meta,
        user_profile=profile,
        documents=doc_payload,
    )

    generated["process"] = meta
    generated["documents"] = doc_payload[:8]

    # Pick images from extracted PDF images of matched documents.
    # Prefer "procedure" section images for the process view,
    # and "introduction" section images for the tool view.
    doc_ids = [d["id"] for d in doc_payload]
    process_image_url = None
    tool_image_url = None

    if doc_ids:
        all_imgs = (
            DocumentImage.query
            .filter(DocumentImage.document_id.in_(doc_ids))
            .order_by(DocumentImage.document_id, DocumentImage.doc_position)
            .all()
        )
        proc_imgs  = [i for i in all_imgs if i.section_name == "procedure"]
        intro_imgs = [i for i in all_imgs if i.section_name == "introduction"]
        fallback   = all_imgs

        def _url(img):
            return f"/static/doc_images/{img.document_id}/{img.filename}"

        if proc_imgs:
            process_image_url = _url(proc_imgs[0])
        elif fallback:
            process_image_url = _url(fallback[0])

        if intro_imgs:
            tool_image_url = _url(intro_imgs[0])
        elif len(fallback) > 1:
            tool_image_url = _url(fallback[1])
        elif fallback:
            tool_image_url = _url(fallback[0])

    generated["process_image_url"] = process_image_url
    generated["tool_image_url"] = tool_image_url

    # Validate AI-recommended SOPs against actual DB doc IDs to prevent hallucinated IDs
    valid_ids = {d["id"] for d in doc_payload}
    ai_sops = generated.get("recommended_sops") or []
    validated_sops = [
        {**s, "id": _safe_int(s.get("id"))}
        for s in ai_sops
        if isinstance(s, dict) and _safe_int(s.get("id")) in valid_ids
    ]

    if validated_sops:
        generated["recommended_sops"] = validated_sops[:8]
    else:
        generated["recommended_sops"] = [
            {
                "id": d["id"],
                "title": d["title"],
                "reason": f"Related to {meta['short_name']} via {d.get('step_type_name') or d.get('step_name') or 'this process step'}.",
            }
            for d in doc_payload
        ][:8]

    return jsonify(generated)