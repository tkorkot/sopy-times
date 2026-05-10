from pathlib import Path
from flask import Flask, render_template, send_file, abort, request, jsonify
from config import Config
from database.db import db
from routes.documents import documents_bp
from routes.search import search_bp
from routes.changes import changes_bp
from routes.summaries import summaries_bp
from routes.drive import drive_bp
from routes.process import process_bp

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

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(documents_bp, url_prefix="/api/documents")
    app.register_blueprint(search_bp,    url_prefix="/api/search")
    app.register_blueprint(changes_bp,   url_prefix="/api/changes")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    app.register_blueprint(drive_bp,    url_prefix="/api/drive")
    app.register_blueprint(process_bp, url_prefix="/api/process")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/documents")
    def documents():
        return render_template("documents.html")

    @app.route("/documents/<int:doc_id>")
    def editor(doc_id):
        return render_template("editor.html", doc_id=doc_id)
    
    @app.route("/process/<process_slug>")
    def process(process_slug):
        process_meta = PROCESS_META.get(process_slug)
        if not process_meta:
            return render_template("404.html"), 404
        return render_template(
            "process.html",
            process=process_meta,
            process_slug=process_slug,
        )
    
    @app.route("/api/process/<process_slug>/personalized", methods=["POST"])
    def personalized_process(process_slug):
        process_meta = PROCESS_META.get(process_slug)

        if not process_meta:
            return jsonify({"error": "Unknown process"}), 404

        profile = request.get_json(silent=True) or {}

        from sqlalchemy import or_
        from database.models import Document, Step, StepType
        from services.ai_service import generate_personalized_process_page

        possible_names = [
            process_meta["title"],        # e.g. "Deposition / Film Formation"
            process_meta["short_name"],   # e.g. "Deposition"
            process_meta["process_area"], # e.g. "Deposition / Film Formation"
        ]

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
                )
            )
            .all()
        )

        doc_payload = []
        for doc in docs:
            doc_payload.append({
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
            })

        print("PROCESS:", process_slug)
        print("POSSIBLE NAMES:", possible_names)
        print("MATCHED SOP DOCS:", len(doc_payload))
        print([
            (
                d["id"],
                d["title"],
                d["doc_type"],
                d["step_name"],
                d["step_type_name"],
                d["process_area"],
            )
            for d in doc_payload[:10]
        ])

        generated = generate_personalized_process_page(
            process=process_meta,
            user_profile=profile,
            documents=doc_payload,
        )

        generated["process"] = process_meta
        generated["documents"] = doc_payload[:8]

        # Force real clickable SOPs from your database.
        generated["recommended_sops"] = [
            {
                "id": d["id"],
                "title": d["title"],
                "reason": f"Related to {process_meta['short_name']} through {d.get('step_type_name') or d.get('step_name') or 'this process step'}."
            }
            for d in doc_payload
        ][:8]

        # Pull images from the DocumentImage records tied to each matched SOP
        from database.models import DocumentImage as _DocImg
        doc_ids = [d["id"] for d in doc_payload]
        process_image_url = None
        tool_image_url = None

        if doc_ids:
            sop_imgs = (
                _DocImg.query
                .filter(_DocImg.document_id.in_(doc_ids))
                .order_by(_DocImg.document_id, _DocImg.doc_position)
                .all()
            )
            if sop_imgs:
                process_image_url = f"/static/doc_images/{sop_imgs[0].document_id}/{sop_imgs[0].filename}"
            if len(sop_imgs) > 1:
                tool_image_url = f"/static/doc_images/{sop_imgs[1].document_id}/{sop_imgs[1].filename}"
            elif sop_imgs:
                tool_image_url = process_image_url

        generated["process_image_url"] = process_image_url
        generated["tool_image_url"] = tool_image_url

        return jsonify(generated)

    @app.route("/documents/<int:doc_id>/pdf")
    def serve_doc_pdf(doc_id):
        from flask import jsonify
        from database.models import Document
        doc = db.session.get(Document, doc_id)
        if not doc or not doc.source_pdf:
            return jsonify({"error": "no source_pdf on document"}), 404

        stored   = doc.source_pdf
        pdf_path = Path(stored)

        # Try the stored path as-is first, then relative to project root
        candidates = [pdf_path, Path(app.root_path) / pdf_path]
        for candidate in candidates:
            if candidate.exists():
                return send_file(str(candidate), mimetype="application/pdf")

        # Neither worked — return debug info so we can see what went wrong
        return jsonify({
            "error":      "PDF file not found on disk",
            "stored_path": stored,
            "root_path":   app.root_path,
            "tried":       [str(c) for c in candidates],
        }), 404
    @app.route("/chatbot")
    def chatbot():
        return render_template("chat.html")

        with app.app_context():
            db.create_all()
    @app.route("/api/chat/process/<process_slug>", methods=["POST"])
    def process_chat(process_slug):
        process_meta = PROCESS_META.get(process_slug)

        if not process_meta:
            return jsonify({"error": "Unknown process"}), 404

        payload = request.get_json(silent=True) or {}

        user_profile = payload.get("user_profile") or {}
        message = payload.get("message") or ""
        chat_history = payload.get("chat_history") or []

        from sqlalchemy import or_
        from database.models import Document, Step, StepType
        from services.chatbot_service import answer_process_chat

        possible_names = [
            process_meta["title"],
            process_meta["short_name"],
            process_meta["process_area"],
        ]

        docs = (
            db.session.query(Document)
            .outerjoin(Step, Document.step_id == Step.id)
            .outerjoin(StepType, Document.step_type_id == StepType.id)
            .filter(
                or_(
                    Step.name.in_(possible_names),
                    StepType.name.in_(possible_names),
                    Document.process_area.in_(possible_names),
                )
            )
            .all()
        )

        doc_payload = []
        for doc in docs:
            doc_payload.append({
                "id": doc.id,
                "title": getattr(doc, "title", ""),
                "process_area": getattr(doc, "process_area", ""),
                "doc_type": getattr(doc, "doc_type", ""),
                "tags": getattr(doc, "tags", []) or [],
                "content": (getattr(doc, "content", "") or "")[:3000],
                "coral_name": getattr(doc, "coral_name", ""),
                "location": getattr(doc, "location", ""),
                "step_name": doc.step.name if getattr(doc, "step", None) else "",
                "step_type_name": doc.step_type.name if getattr(doc, "step_type", None) else "",
            })

        print("CHAT PROCESS:", process_slug)
        print("CHAT MATCHED DOCS:", len(doc_payload))

        result = answer_process_chat(
            process=process_meta,
            user_profile=user_profile,
            documents=doc_payload,
            message=message,
            chat_history=chat_history,
        )

        return jsonify(result)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
