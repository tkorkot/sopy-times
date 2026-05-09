"""CRUD operations for Documents and their relationships."""

from database.db import db
from database.models import Document, DocumentRelation


def get_all_documents() -> list[dict]:
    docs = Document.query.order_by(Document.updated_at.desc()).all()
    return [d.to_dict() for d in docs]


def get_document(doc_id: int) -> dict | None:
    doc = Document.query.get(doc_id)
    return doc.to_dict() if doc else None


def create_document(
    title: str,
    content: str,
    process_area: str,
    tags: list[str],
    coral_name: str | None = None,
    location: str | None = None,
    category: str | None = None,
    contact: str | None = None,
    last_revision: str | None = None,
    sop_version: str | None = None,
    author: str | None = None,
    structured_content: str | None = None,
    source_pdf: str | None = None,
) -> dict:
    doc = Document(
        title              = title,
        content            = content,
        process_area       = process_area,
        tags               = ",".join(tags),
        coral_name         = coral_name,
        location           = location,
        category           = category,
        contact            = contact,
        last_revision      = last_revision,
        sop_version        = sop_version,
        author             = author,
        structured_content = structured_content,
        source_pdf         = source_pdf,
    )
    db.session.add(doc)
    db.session.commit()
    return doc.to_dict()


def update_document(doc_id: int, **fields) -> dict | None:
    doc = Document.query.get(doc_id)
    if not doc:
        return None

    if "title" in fields:
        doc.title = fields["title"]
    if "content" in fields:
        doc.content = fields["content"]
    if "process_area" in fields:
        doc.process_area = fields["process_area"]
    if "tags" in fields:
        doc.tags = ",".join(fields["tags"])

    doc.version += 1
    db.session.commit()
    return doc.to_dict()


def delete_document(doc_id: int) -> bool:
    doc = Document.query.get(doc_id)
    if not doc:
        return False
    db.session.delete(doc)
    db.session.commit()
    return True


def get_related_documents(doc_id: int) -> dict:
    """Return upstream, downstream, and similar documents for a given SOP."""
    relations = DocumentRelation.query.filter(
        (DocumentRelation.source_id == doc_id) | (DocumentRelation.target_id == doc_id)
    ).all()

    result = {"upstream": [], "downstream": [], "similar": []}
    for rel in relations:
        if rel.source_id == doc_id:
            other = Document.query.get(rel.target_id)
        else:
            other = Document.query.get(rel.source_id)

        if other:
            result.setdefault(rel.relation_type, []).append(other.to_dict())

    return result


def add_relation(source_id: int, target_id: int, relation_type: str) -> bool:
    existing = DocumentRelation.query.filter_by(
        source_id=source_id, target_id=target_id
    ).first()
    if existing:
        return False
    rel = DocumentRelation(source_id=source_id, target_id=target_id, relation_type=relation_type)
    db.session.add(rel)
    db.session.commit()
    return True
