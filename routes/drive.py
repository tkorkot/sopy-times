import os
from flask import Blueprint, jsonify
from services import drive_service

drive_bp = Blueprint("drive", __name__)


@drive_bp.get("/inspect")
def inspect():
    """
    GET /api/drive/inspect
    Returns a summary of what is in the configured Drive folder without downloading.
    """
    try:
        summary = drive_service.inspect_folder()
        return jsonify(summary)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Drive error: {e}"}), 500
