"""
Run once to populate the database with sample SOPs and their relationships.
  uv run python seed.py
"""

import os
from app import create_app
from database.db import db
from database.models import Document, DocumentRelation

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "data", "sample_sops")

SOPS = [
    {
        "file":          "plasma_cleaning.md",
        "title":         "Plasma Pre-Cleaning (PMC)",
        "process_area":  "Plasma / Surface Preparation",
        "tags":          ["plasma", "precleaning", "surface prep", "Ar", "O2"],
        "coral_name":    "Plasma-Precleaner-PMC",
        "location":      "L04",
        "category":      "Plasma / Surface Preparation",
        "contact":       "Process Engineering, Lab Support",
        "last_revision": "05/09/2025",
        "sop_version":   "1.0",
        "author":        "Lab Staff",
    },
    {
        "file":          "solderball_reflow.md",
        "title":         "Solderball Reflow",
        "process_area":  "Soldering / Flip-Chip Assembly",
        "tags":          ["solder", "reflow", "flip-chip", "bump height", "SAC305"],
        "coral_name":    "Reflow-Heller-1800EXL",
        "location":      "U12",
        "category":      "Soldering / Flip-Chip Assembly",
        "contact":       "Assembly Process Engineering, Lab Support",
        "last_revision": "05/09/2025",
        "sop_version":   "1.0",
        "author":        "Lab Staff",
    },
    {
        "file":          "material_handling.md",
        "title":         "Substrate Material Handling",
        "process_area":  "Material Handling / ESD / Contamination Control",
        "tags":          ["handling", "ESD", "storage", "substrate", "cleanroom", "contamination"],
        "coral_name":    "N/A (General Lab Procedure)",
        "location":      "All cleanroom and lab areas",
        "category":      "Material Handling / ESD / Contamination Control",
        "contact":       "Lab Support, Process Engineering",
        "last_revision": "05/09/2025",
        "sop_version":   "1.0",
        "author":        "Lab Staff",
    },
]

# (source_title, target_title, relation_type)
RELATIONS = [
    ("Substrate Material Handling", "Plasma Pre-Cleaning (PMC)", "downstream"),
    ("Plasma Pre-Cleaning (PMC)",   "Solderball Reflow",         "downstream"),
]


def seed():
    app = create_app()
    with app.app_context():
        if Document.query.count() > 0:
            print("Database already seeded — skipping.")
            return

        title_to_id = {}
        for sop in SOPS:
            path = os.path.join(SAMPLE_DIR, sop["file"])
            with open(path, encoding="utf-8") as f:
                content = f.read()

            doc = Document(
                title         = sop["title"],
                content       = content,
                process_area  = sop["process_area"],
                tags          = ",".join(sop["tags"]),
                coral_name    = sop["coral_name"],
                location      = sop["location"],
                category      = sop["category"],
                contact       = sop["contact"],
                last_revision = sop["last_revision"],
                sop_version   = sop["sop_version"],
                author        = sop["author"],
            )
            db.session.add(doc)
            db.session.flush()
            title_to_id[sop["title"]] = doc.id
            print(f"  Created: {sop['title']} (id={doc.id})")

        for source_title, target_title, rel_type in RELATIONS:
            rel = DocumentRelation(
                source_id     = title_to_id[source_title],
                target_id     = title_to_id[target_title],
                relation_type = rel_type,
            )
            db.session.add(rel)
            print(f"  Linked: {source_title} → {target_title} ({rel_type})")

        db.session.commit()
        print("Seed complete.")


if __name__ == "__main__":
    seed()
