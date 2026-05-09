from flask import Flask, render_template
from config import Config
from database.db import db
from routes.documents import documents_bp
from routes.search import search_bp
from routes.changes import changes_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(documents_bp, url_prefix="/api/documents")
    app.register_blueprint(search_bp,    url_prefix="/api/search")
    app.register_blueprint(changes_bp,   url_prefix="/api/changes")

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

    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
