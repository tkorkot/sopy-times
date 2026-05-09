import json
import os
from flask import Blueprint, jsonify, request, current_app
from werkzeug.utils import secure_filename
from services import document_service
from services.pdf_service import extract_from_pdf, sections_to_markdown

UPLOAD_FOLDER = "uploads"
ALLOWED_EXT = {"pdf"}

documents_bp = Blueprint("documents", __name__)


@documents_bp.get("/")
def list_documents():
    return jsonify(document_service.get_all_documents())


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
    POST /api/documents/upload  (multipart/form-data, field name: file)
    Accepts a PDF, extracts content and metadata, creates a Document record.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted"}), 400

    # Save to uploads/
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    filename  = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # Extract and parse
    extracted = extract_from_pdf(save_path)
    meta      = extracted["metadata"]
    sections  = extracted["sections"]
    content   = sections_to_markdown(sections) if sections else extracted["raw_text"]

    doc = document_service.create_document(
        title              = extracted["title"],
        content            = content,
        process_area       = extracted["process_area"],
        tags               = extracted["tags"],
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
    return jsonify(doc), 201


@documents_bp.post("/<int:doc_id>/relations")
def add_relation(doc_id):
    data = request.get_json()
    ok = document_service.add_relation(doc_id, data["target_id"], data["relation_type"])
    return jsonify({"ok": ok})
