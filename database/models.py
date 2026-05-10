from datetime import datetime, timezone
from database.db import db


class Step(db.Model):
    """Top-level process step, e.g. 'Deposition', 'Etch'."""
    __tablename__ = "steps"

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)

    types     = db.relationship("StepType", back_populates="step", cascade="all, delete-orphan")
    documents = db.relationship("Document",  back_populates="step")

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class StepType(db.Model):
    """Sub-category within a Step, e.g. 'Chemical', 'Physical' under Deposition."""
    __tablename__ = "step_types"
    __table_args__ = (db.UniqueConstraint("step_id", "name"),)

    id      = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey("steps.id"), nullable=False)
    name    = db.Column(db.String(255), nullable=False)

    step      = db.relationship("Step", back_populates="types")
    documents = db.relationship("Document", back_populates="step_type")

    def to_dict(self):
        return {"id": self.id, "step_id": self.step_id, "name": self.name}


class Document(db.Model):
    __tablename__ = "documents"

    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(255), nullable=False)
    content      = db.Column(db.Text, nullable=False)
    process_area = db.Column(db.String(100))
    tags         = db.Column(db.String(500))
    version      = db.Column(db.Integer, default=1)

    # Folder-hierarchy FKs
    step_id      = db.Column(db.Integer, db.ForeignKey("steps.id"),      nullable=True)
    step_type_id = db.Column(db.Integer, db.ForeignKey("step_types.id"), nullable=True)
    doc_type     = db.Column(db.String(20), default="SOP")  # "SOP" | "INFO"

    # SOP header metadata
    coral_name     = db.Column(db.String(200))
    location       = db.Column(db.String(100))
    category       = db.Column(db.String(150))
    contact        = db.Column(db.String(300))
    last_revision  = db.Column(db.String(50))
    sop_version    = db.Column(db.String(50))
    author         = db.Column(db.String(200))

    # Full extracted content as JSON sections
    structured_content = db.Column(db.Text)
    source_pdf         = db.Column(db.String(500))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    step      = db.relationship("Step",     back_populates="documents")
    step_type = db.relationship("StepType", back_populates="documents")
    changes   = db.relationship("Change", back_populates="document", cascade="all, delete-orphan")
    images    = db.relationship("DocumentImage", back_populates="document", cascade="all, delete-orphan")
    related_to   = db.relationship("DocumentRelation", foreign_keys="DocumentRelation.source_id",
                                   back_populates="source", cascade="all, delete-orphan")
    related_from = db.relationship("DocumentRelation", foreign_keys="DocumentRelation.target_id",
                                   back_populates="target", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":           self.id,
            "title":        self.title,
            "content":      self.content,
            "process_area": self.process_area,
            "tags":         self.tags.split(",") if self.tags else [],
            "version":      self.version,
            "doc_type":     self.doc_type,
            "step_id":      self.step_id,
            "step_type_id": self.step_type_id,
            "step_name":    self.step.name      if self.step      else None,
            "step_type_name": self.step_type.name if self.step_type else None,
            "coral_name":    self.coral_name,
            "location":      self.location,
            "category":      self.category,
            "contact":       self.contact,
            "last_revision": self.last_revision,
            "sop_version":   self.sop_version,
            "author":        self.author,
            "structured_content": self.structured_content,
            "source_pdf":    self.source_pdf,
            "created_at":    self.created_at.isoformat() if self.created_at else None,
            "updated_at":    self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentImage(db.Model):
    """An image extracted from a document's source PDF."""
    __tablename__ = "document_images"

    id           = db.Column(db.Integer, primary_key=True)
    document_id  = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    filename     = db.Column(db.String(500), nullable=False)   # file under static/doc_images/<doc_id>/
    page_number  = db.Column(db.Integer, default=0)            # 0-indexed page
    page_total   = db.Column(db.Integer, default=1)
    position_y   = db.Column(db.Float, default=0.0)            # 0-1 within the page
    doc_position = db.Column(db.Float, default=0.0)            # 0-1 across the whole document
    section_name = db.Column(db.String(50), default="procedure")  # detected SOP section
    width        = db.Column(db.Integer)
    height       = db.Column(db.Integer)
    is_replaced  = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    document = db.relationship("Document", back_populates="images")

    def to_dict(self):
        from services.image_service import image_url
        return {
            "id":           self.id,
            "document_id":  self.document_id,
            "filename":     self.filename,
            "url":          image_url(self.document_id, self.filename),
            "page_number":  self.page_number,
            "page_total":   self.page_total,
            "position_y":   self.position_y,
            "doc_position": self.doc_position,
            "section_name": self.section_name,
            "width":        self.width,
            "height":       self.height,
            "is_replaced":  self.is_replaced,
        }


class DocumentRelation(db.Model):
    __tablename__ = "document_relations"
    __table_args__ = (db.UniqueConstraint("source_id", "target_id"),)

    id            = db.Column(db.Integer, primary_key=True)
    source_id     = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    target_id     = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    relation_type = db.Column(db.String(50))  # "upstream" | "downstream" | "similar"

    source = db.relationship("Document", foreign_keys=[source_id], back_populates="related_to")
    target = db.relationship("Document", foreign_keys=[target_id], back_populates="related_from")


class Change(db.Model):
    __tablename__ = "changes"

    id               = db.Column(db.Integer, primary_key=True)
    document_id      = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    original_content = db.Column(db.Text, nullable=False)
    new_content      = db.Column(db.Text, nullable=False)
    description      = db.Column(db.String(500))
    status           = db.Column(db.String(20), default="pending")  # pending | applied | rejected
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    document  = db.relationship("Document", back_populates="changes")
    proposals = db.relationship("ChangeProposal", back_populates="change", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":          self.id,
            "document_id": self.document_id,
            "description": self.description,
            "status":      self.status,
            "created_at":  self.created_at.isoformat(),
            "proposals":   [p.to_dict() for p in self.proposals],
        }


class ChangeProposal(db.Model):
    __tablename__ = "change_proposals"

    id                 = db.Column(db.Integer, primary_key=True)
    change_id          = db.Column(db.Integer, db.ForeignKey("changes.id"), nullable=False)
    target_document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    original_section   = db.Column(db.Text)
    proposed_section   = db.Column(db.Text)
    reason             = db.Column(db.Text)
    confidence         = db.Column(db.Float)
    status             = db.Column(db.String(20), default="pending")

    change = db.relationship("Change", back_populates="proposals")

    def to_dict(self):
        return {
            "id":                 self.id,
            "change_id":          self.change_id,
            "target_document_id": self.target_document_id,
            "original_section":   self.original_section,
            "proposed_section":   self.proposed_section,
            "reason":             self.reason,
            "confidence":         self.confidence,
            "status":             self.status,
        }
