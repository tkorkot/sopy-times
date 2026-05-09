from datetime import datetime, timezone
from database.db import db


class Document(db.Model):
    __tablename__ = "documents"

    id            = db.Column(db.Integer, primary_key=True)
    title         = db.Column(db.String(255), nullable=False)
    content       = db.Column(db.Text, nullable=False)
    process_area  = db.Column(db.String(100))       # e.g. "Plasma Cleaning", "Soldering"
    tags          = db.Column(db.String(500))        # comma-separated
    version       = db.Column(db.Integer, default=1)
    # Metadata matching real SOP header fields
    coral_name    = db.Column(db.String(200))        # Equipment reservation system name
    location      = db.Column(db.String(100))        # Lab location code(s)
    category      = db.Column(db.String(150))        # Process category
    contact       = db.Column(db.String(300))        # Point-of-contact names
    last_revision      = db.Column(db.String(50))    # Human-readable date string
    sop_version        = db.Column(db.String(50))    # e.g. "1.0", "Draft"
    author             = db.Column(db.String(200))
    # Structured JSON extracted from PDF — keyed by section name
    # {"introduction": "...", "safety": "...", "procedure": "...", "appendix": "..."}
    structured_content = db.Column(db.Text)
    # Path to the original uploaded PDF (relative to project root)
    source_pdf         = db.Column(db.String(500))
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    changes     = db.relationship("Change", back_populates="document", cascade="all, delete-orphan")
    related_to  = db.relationship("DocumentRelation", foreign_keys="DocumentRelation.source_id",
                                  back_populates="source", cascade="all, delete-orphan")
    related_from = db.relationship("DocumentRelation", foreign_keys="DocumentRelation.target_id",
                                   back_populates="target", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":            self.id,
            "title":         self.title,
            "content":       self.content,
            "process_area":  self.process_area,
            "tags":          self.tags.split(",") if self.tags else [],
            "version":       self.version,
            "coral_name":    self.coral_name,
            "location":      self.location,
            "category":      self.category,
            "contact":       self.contact,
            "last_revision": self.last_revision,
            "sop_version":   self.sop_version,
            "author":             self.author,
            "structured_content": self.structured_content,  # raw JSON string
            "source_pdf":         self.source_pdf,
            "created_at":         self.created_at.isoformat(),
            "updated_at":         self.updated_at.isoformat(),
        }


class DocumentRelation(db.Model):
    """Tracks upstream / downstream / similar relationships between SOPs."""
    __tablename__ = "document_relations"
    __table_args__ = (db.UniqueConstraint("source_id", "target_id"),)

    id              = db.Column(db.Integer, primary_key=True)
    source_id       = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    target_id       = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    relation_type   = db.Column(db.String(50))  # "upstream", "downstream", "similar"

    source = db.relationship("Document", foreign_keys=[source_id], back_populates="related_to")
    target = db.relationship("Document", foreign_keys=[target_id], back_populates="related_from")


class Change(db.Model):
    """A recorded edit to a document."""
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
            "id":               self.id,
            "document_id":      self.document_id,
            "description":      self.description,
            "status":           self.status,
            "created_at":       self.created_at.isoformat(),
            "proposals":        [p.to_dict() for p in self.proposals],
        }


class ChangeProposal(db.Model):
    """AI-suggested edit to a related document, generated from a Change."""
    __tablename__ = "change_proposals"

    id                 = db.Column(db.Integer, primary_key=True)
    change_id          = db.Column(db.Integer, db.ForeignKey("changes.id"), nullable=False)
    target_document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    original_section   = db.Column(db.Text)
    proposed_section   = db.Column(db.Text)
    reason             = db.Column(db.Text)
    confidence         = db.Column(db.Float)       # 0.0 – 1.0
    status             = db.Column(db.String(20), default="pending")

    change = db.relationship("Change", back_populates="proposals")

    def to_dict(self):
        return {
            "id":                  self.id,
            "change_id":           self.change_id,
            "target_document_id":  self.target_document_id,
            "original_section":    self.original_section,
            "proposed_section":    self.proposed_section,
            "reason":              self.reason,
            "confidence":          self.confidence,
            "status":              self.status,
        }
