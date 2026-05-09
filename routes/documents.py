import json
import os
from pathlib import Path
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename
from database.db import db
from database.models import Step
from services import document_service
from services.pdf_service import extract_from_pdf, sections_to_markdown

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EXT = {"pdf"}

documents_bp = Blueprint("documents", __name__)


@documents_bp.get("/")
def list_documents():
    return jsonify(document_service.get_all_documents())


@documents_bp.get("/steps")
def get_steps():
    """
    GET /api/documents/steps
    Returns all Steps with their StepTypes — used to populate the upload form dropdowns.
    """
    steps = Step.query.order_by(Step.name).all()
    return jsonify([
        {
            "id":    s.id,
            "name":  s.name,
            "types": [{"id": t.id, "name": t.name} for t in s.types],
        }
        for s in steps
    ])


@documents_bp.get("/<int:doc_id>")
def get_document(doc_id):
    doc = document_service.get_document(doc_id)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    related = document_service.get_related_documents(doc_id)
    return jsonify({**doc, "related": related})


@documents_bp.post("/")
def create_document():
    data = request.get_json()
    doc = document_service.create_document(
        title=data["title"],
        content=data["content"],
        process_area=data.get("process_area", ""),
        tags=data.get("tags", []),
    )
    return jsonify(doc), 201


@documents_bp.put("/<int:doc_id>")
def update_document(doc_id):
    data = request.get_json()
    doc = document_service.update_document(doc_id, **data)
    if not doc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(doc)


@documents_bp.delete("/<int:doc_id>")
def delete_document(doc_id):
    if not document_service.delete_document(doc_id):
        return jsonify({"error": "Not found"}), 404
    return jsonify({"ok": True})


@documents_bp.post("/upload")
def upload_pdf():
    """
    POST /api/documents/upload  (multipart/form-data)
    Fields:
      file           — PDF file (required)
      step_name      — process step name, e.g. "Deposition" (required)
      step_type_name — sub-type, e.g. "Chemical" (optional)
      doc_type       — "SOP" or "INFO" (default: "SOP")
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    step_name      = request.form.get("step_name", "").strip()
    step_type_name = request.form.get("step_type_name", "").strip()
    doc_type       = request.form.get("doc_type", "SOP").strip().upper()
    if doc_type not in ("SOP", "INFO"):
        doc_type = "SOP"

    # Resolve step / step_type (create if new)
    step_id = step_type_id = None
    if step_name:
        try:
            step      = document_service.get_or_create_step(step_name)
            step_id   = step.id
            if step_type_name:
                stype        = document_service.get_or_create_step_type(step, step_type_name)
                step_type_id = stype.id
            db.session.commit()
        except Exception as e:
            return jsonify({"error": f"Failed to resolve step/type: {e}"}), 500

    # Save uploaded file
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename  = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # Extract PDF content
    try:
        extracted = extract_from_pdf(save_path)
    except Exception as e:
        return jsonify({"error": f"PDF extraction failed: {e}"}), 500

    # Save to database
    try:
        meta     = extracted["metadata"]
        sections = extracted["sections"]
        content  = sections_to_markdown(sections) if sections else extracted["raw_text"]

        doc = document_service.create_document(
            title              = extracted["title"],
            content            = content,
            process_area       = extracted.get("process_area", ""),
            tags               = extracted.get("tags", []),
            step_id            = step_id,
            step_type_id       = step_type_id,
            doc_type           = doc_type,
            coral_name         = meta.get("coral_name"),
            location           = meta.get("location"),
            category           = meta.get("category"),
            contact            = meta.get("contact"),
            last_revision      = meta.get("last_revision"),
            sop_version        = meta.get("sop_version"),
            author             = meta.get("author"),
            structured_content = json.dumps(sections),
            source_pdf         = save_path,
        )
    except Exception as e:
        return jsonify({"error": f"Failed to save document: {e}"}), 500

    return jsonify(doc), 201


@documents_bp.get("/<int:doc_id>/pdf")
def serve_pdf(doc_id):
    """Serve the original PDF file for inline viewing."""
    from flask import send_file, abort, current_app
    doc = document_service.get_document(doc_id)
    if not doc or not doc.get("source_pdf"):
        abort(404)

    pdf_path = Path(doc["source_pdf"])
    if not pdf_path.is_absolute():
        pdf_path = Path(current_app.root_path) / pdf_path

    if not pdf_path.exists():
        abort(404)

    return send_file(str(pdf_path), mimetype="application/pdf")


@documents_bp.post("/<int:doc_id>/relations")
def add_relation(doc_id):
    data = request.get_json()
    ok = document_service.add_relation(doc_id, data["target_id"], data["relation_type"])
    return jsonify({"ok": ok})
