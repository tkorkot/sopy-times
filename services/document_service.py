"""CRUD operations for Documents and their relationships."""

from database.db import db
from database.models import Document, DocumentRelation, Step, StepType


# ── Step / StepType helpers ──────────────────────────────────────────────────

def get_or_create_step(name: str) -> Step:
    step = Step.query.filter_by(name=name).first()
    if not step:
        step = Step(name=name)
        db.session.add(step)
        db.session.flush()
    return step


def get_or_create_step_type(step: Step, name: str) -> StepType:
    stype = StepType.query.filter_by(step_id=step.id, name=name).first()
    if not stype:
        stype = StepType(step_id=step.id, name=name)
        db.session.add(stype)
        db.session.flush()
    return stype


# ── Document CRUD ────────────────────────────────────────────────────────────

def get_all_documents() -> list[dict]:
    docs = Document.query.order_by(Document.step_id, Document.step_type_id, Document.title).all()
    return [d.to_dict() for d in docs]


def get_document(doc_id: int) -> dict | None:
    doc = Document.query.get(doc_id)
    return doc.to_dict() if doc else None


def create_document(
    title: str,
    content: str,
    process_area: str = "",
    tags: list[str] | None = None,
    step_id: int | None = None,
    step_type_id: int | None = None,
    doc_type: str = "SOP",
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
        tags               = ",".join(tags) if tags else "",
        step_id            = step_id,
        step_type_id       = step_type_id,
        doc_type           = doc_type,
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
    for key in ("title", "content", "process_area"):
        if key in fields:
            setattr(doc, key, fields[key])
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
    relations = DocumentRelation.query.filter(
        (DocumentRelation.source_id == doc_id) | (DocumentRelation.target_id == doc_id)
    ).all()

    result: dict[str, list] = {"upstream": [], "downstream": [], "similar": []}
    for rel in relations:
        other_id = rel.target_id if rel.source_id == doc_id else rel.source_id
        other = Document.query.get(other_id)
        if other:
            result.setdefault(rel.relation_type, []).append(other.to_dict())
    return result


def add_relation(source_id: int, target_id: int, relation_type: str) -> bool:
    if DocumentRelation.query.filter_by(source_id=source_id, target_id=target_id).first():
        return False
    rel = DocumentRelation(source_id=source_id, target_id=target_id, relation_type=relation_type)
    db.session.add(rel)
    db.session.commit()
    return True
