from pathlib import Path
from flask import Flask, render_template, send_file, abort
from config import Config
from database.db import db
from routes.documents import documents_bp
from routes.search import search_bp
from routes.changes import changes_bp
from routes.summaries import summaries_bp
from routes.drive import drive_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(documents_bp, url_prefix="/api/documents")
    app.register_blueprint(search_bp,    url_prefix="/api/search")
    app.register_blueprint(changes_bp,   url_prefix="/api/changes")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    app.register_blueprint(drive_bp,    url_prefix="/api/drive")

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

    @app.route("/documents/<int:doc_id>/pdf")
    def serve_doc_pdf(doc_id):
        from flask import jsonify
        from database.models import Document
        doc = Document.query.get(doc_id)
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

    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
