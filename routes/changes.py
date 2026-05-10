from flask import Blueprint, jsonify, request
from database.db import db
from database.models import Change, ChangeProposal, Document
from services import change_service, ai_service, document_service

changes_bp = Blueprint("changes", __name__)


@changes_bp.get("/")
def list_changes():
    doc_id = request.args.get("doc_id", type=int)
    return jsonify(change_service.get_all_changes(doc_id=doc_id))


@changes_bp.post("/")
def create_change():
    """
    POST /api/changes
    Body: { "document_id": int, "new_content": str, "description": str }
    Saves the change, runs AI propagation, returns change + proposals.
    """
    data = request.get_json()
    doc = document_service.get_document(data["document_id"])
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    change = change_service.record_change(
        doc_id=data["document_id"],
        original_content=doc["content"],
        new_content=data["new_content"],
        description=data.get("description", ""),
    )
    return jsonify(change), 201


@changes_bp.post("/<int:change_id>/apply")
def apply_change(change_id):
    """Apply the primary change to its document."""
    change = change_service.apply_change(change_id)
    if not change:
        return jsonify({"error": "Not found"}), 404
    return jsonify(change)


@changes_bp.post("/proposals/<int:proposal_id>/apply")
def apply_proposal(proposal_id):
    proposal = change_service.apply_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Not found"}), 404
    return jsonify(proposal)


@changes_bp.post("/proposals/<int:proposal_id>/reject")
def reject_proposal(proposal_id):
    proposal = change_service.reject_proposal(proposal_id)
    if not proposal:
        return jsonify({"error": "Not found"}), 404
    return jsonify(proposal)


@changes_bp.post("/suggest-edit")
def suggest_edit():
    """
    POST /api/changes/suggest-edit
    Body: { "document_id": int, "edit_description": str }
    Returns:
      { "suggested_content": str,       # full updated document
        "original_snippet":  str,       # exact text that changes
        "replacement":       str,       # what it becomes
        "summary":           str }      # one-sentence description
    """
    data = request.get_json()
    doc = document_service.get_document(data["document_id"])
    if not doc:
        return jsonify({"error": "Document not found"}), 404

    result = ai_service.generate_edit_suggestions(doc, data["edit_description"])
    return jsonify({
        "suggested_content": result.get("full_content", ""),
        "original_snippet":  result.get("original_snippet", ""),
        "replacement":       result.get("replacement", ""),
        "summary":           result.get("summary", ""),
        "edit_type":         result.get("edit_type", "replace"),
    })


@changes_bp.get("/<int:change_id>/annotated-pdf")
def annotated_pdf(change_id):
    """
    GET /api/changes/<id>/annotated-pdf?snippet=<original_snippet>
    Serve the source PDF with highlights on the changed text.
    """
    from io import BytesIO
    import fitz
    from flask import send_file, current_app
    from pathlib import Path
    from database.models import Change, Document

    change = db.session.get(Change, change_id)
    if not change:
        return jsonify({"error": "Change not found"}), 404

    doc_record = db.session.get(Document, change.document_id)
    if not doc_record or not doc_record.source_pdf:
        return jsonify({"error": "No source PDF"}), 404

    pdf_path = Path(doc_record.source_pdf)
    if not pdf_path.is_absolute():
        pdf_path = Path(current_app.root_path) / pdf_path
    if not pdf_path.exists():
        return jsonify({"error": "PDF not found on disk"}), 404

    hint        = request.args.get("snippet", "").strip()
    replacement = request.args.get("replacement", "").strip()
    edit_type   = request.args.get("edit_type", "replace").strip()  # "replace"|"add"|"delete"
    label       = change.description or "Changed"
    pdf         = fitz.open(str(pdf_path))
    found_any   = False
    all_hits    = []   # list of (page, rect)

    if edit_type == "add":
        # Pure addition — nothing to highlight; show green box on the last page
        last_page = pdf[-1]
        pw = last_page.rect.width
        ph = last_page.rect.height
        disp = replacement[:400] + ("…" if len(replacement) > 400 else "")
        fa = last_page.add_freetext_annot(
            fitz.Rect(10, max(ph - 120, 10), pw - 10, ph - 10),
            f"✚ ADDED AT END:\n{disp}",
            fontsize=8,
            text_color=[0, 0.45, 0.1],
            fill_color=[0.88, 1.0, 0.88],
        )
        fa.update()
    else:
        # Build a list of candidates to try, from most to least specific
        candidates = _search_candidates(hint, change.original_content, change.new_content)

        for candidate in candidates:
            if len(candidate) < 4:
                continue
            for page in pdf:
                hits = page.search_for(candidate, quads=False)
                for rect in hits:
                    hl = page.add_highlight_annot(rect)
                    hl.set_colors(stroke=[1, 0.84, 0])   # yellow
                    hl.update()
                    found_any = True
                    all_hits.append((page, rect))

        # Green freetext box below every highlighted rect
        if replacement:
            disp = replacement[:250] + ("…" if len(replacement) > 250 else "")
            if all_hits:
                for hit_page, hit_rect in all_hits:
                    pw = hit_page.rect.width
                    ph = hit_page.rect.height
                    ax0 = max(5, min(hit_rect.x0, pw - 305))
                    ay0 = min(hit_rect.y1 + 4, ph - 65)
                    fa = hit_page.add_freetext_annot(
                        fitz.Rect(ax0, ay0, ax0 + 300, ay0 + 60),
                        f"→ NEW: {disp}",
                        fontsize=8,
                        text_color=[0, 0.45, 0.1],
                        fill_color=[0.88, 1.0, 0.88],
                    )
                    fa.update()
            else:
                # No hits found — add one box at top of page 1 as fallback
                fa = pdf[0].add_freetext_annot(
                    fitz.Rect(10, 40, 310, 100),
                    f"→ NEW: {disp}",
                    fontsize=8,
                    text_color=[0, 0.45, 0.1],
                    fill_color=[0.88, 1.0, 0.88],
                )
                fa.update()

    # Always add a summary note on page 1 so the user sees something
    note_text = f"✏ {label}"
    if edit_type != "add" and not found_any:
        note_text += "\n(Exact location could not be highlighted automatically)"
    annot = pdf[0].add_text_annot(fitz.Point(10, 10), note_text)
    annot.set_colors(stroke=[1, 0.6, 0], fill=[1, 0.95, 0.6])
    annot.update()

    buf = BytesIO()
    pdf.save(buf, garbage=3, deflate=True)
    buf.seek(0)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"annotated_{doc_record.id}.pdf")


def _search_candidates(hint: str, original: str, new_content: str) -> list[str]:
    """
    Return a prioritised list of strings to search for in the PDF.
    Raw numbers/values survive AI reformatting and match the PDF best.
    """
    import re
    candidates = []

    # 1. Numbers with units and ratios — most reliable match against PDF text
    #    e.g. "80:20", "200 W", "5 sccm", "300°C", "1e-6 Torr"
    if hint:
        numbers = re.findall(
            r'\d[\d:./]*\s*(?:sccm|mTorr|Torr|°C|°F|W|V|A|rpm|min|sec|%|nm|µm|um|mm|kV|mA|MHz|kHz|Hz)?',
            hint, re.IGNORECASE,
        )
        candidates.extend(n.strip() for n in numbers if len(n.strip()) >= 2)

    # 2. Quoted or capitalised proper nouns from the hint
    if hint:
        words = re.findall(r'[A-Z][A-Za-z0-9\-]{3,}', hint)
        candidates.extend(words)

    # 3. Lines from original content not in new content (content-level diff)
    for line in original.splitlines():
        line = line.strip().lstrip('#').strip()
        if len(line) > 15 and line not in new_content:
            # Strip markdown formatting before searching
            clean = re.sub(r'[*_`#>\-]', '', line).strip()
            if len(clean) > 10:
                candidates.append(clean[:60])

    return candidates
