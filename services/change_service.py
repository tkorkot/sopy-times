"""
Orchestrates the full change-and-propagate workflow:
  1. Save the change to the database
  2. Call AI to find related documents that need similar edits
  3. Store AI proposals for the user to review and accept/reject
"""

from database.db import db
from database.models import Change, ChangeProposal, Document
from services import ai_service
from services import document_service


def record_change(doc_id: int, original_content: str, new_content: str, description: str) -> dict:
    """Save an edit and generate AI propagation proposals for related documents."""
    change = Change(
        document_id=doc_id,
        original_content=original_content,
        new_content=new_content,
        description=description,
        status="pending",
    )
    db.session.add(change)
    db.session.flush()  # get change.id before commit

    changed_doc = document_service.get_document(doc_id)
    all_docs = document_service.get_all_documents()

    proposals = ai_service.suggest_change_propagation(
        changed_doc=changed_doc,
        original_content=original_content,
        new_content=new_content,
        all_documents=all_docs,
    )

    for p in proposals:
        proposal = ChangeProposal(
            change_id=change.id,
            target_document_id=p["target_document_id"],
            original_section=p.get("original_section", ""),
            proposed_section=p.get("proposed_section", ""),
            reason=p.get("reason", ""),
            confidence=p.get("confidence", 0.0),
        )
        db.session.add(proposal)

    db.session.commit()
    return change.to_dict()


def apply_change(change_id: int) -> dict | None:
    """Apply the primary change — update the document content."""
    change = Change.query.get(change_id)
    if not change:
        return None

    document_service.update_document(change.document_id, content=change.new_content)
    change.status = "applied"
    db.session.commit()
    return change.to_dict()


def apply_proposal(proposal_id: int) -> dict | None:
    """Accept a single AI propagation proposal and update the target document."""
    proposal = ChangeProposal.query.get(proposal_id)
    if not proposal:
        return None

    doc = Document.query.get(proposal.target_document_id)
    if doc and proposal.original_section in doc.content:
        doc.content = doc.content.replace(proposal.original_section, proposal.proposed_section, 1)
        doc.version += 1

    proposal.status = "applied"
    db.session.commit()
    return proposal.to_dict()


def reject_proposal(proposal_id: int) -> dict | None:
    proposal = ChangeProposal.query.get(proposal_id)
    if not proposal:
        return None
    proposal.status = "rejected"
    db.session.commit()
    return proposal.to_dict()


def get_all_changes() -> list[dict]:
    changes = Change.query.order_by(Change.created_at.desc()).all()
    return [c.to_dict() for c in changes]
