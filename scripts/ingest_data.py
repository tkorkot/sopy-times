"""
Ingest the local data/ folder into the database.

Assumes the data/ folder already exists (downloaded from Drive or placed manually).
Run this after downloading to build/refresh the database.

Folder structure:
    data/
      <N> - <STEP>/         →  Step  (number prefix stripped)
        <TYPE>/             →  StepType
          SOP/              →  doc_type = "SOP"
          Information/      →  doc_type = "INFO"
        Information/        →  step-level INFO (no StepType)

Usage:
    python scripts/ingest_data.py            # ingest everything new
    python scripts/ingest_data.py --dry-run  # print what would be imported
"""

import argparse
import json
import os
os.environ.setdefault("MUPDF_QUIET", "1")  # suppress MuPDF structure-tree warnings
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from database.db import db
from database.models import Document
from services.document_service import (
    create_document,
    get_or_create_step,
    get_or_create_step_type,
)
from services.pdf_service import extract_from_pdf, sections_to_markdown
from services.image_service import extract_images
from database.models import DocumentImage

DATA_ROOT = Path(os.getenv("DRIVE_DOWNLOAD_DIR", "data"))

DOC_TYPE_DIRS = {"SOP", "Information", "Image"}
DOC_TYPE_MAP  = {"SOP": "SOP", "Information": "INFO", "Image": "IMAGE"}


def strip_number_prefix(name: str) -> str:
    return re.sub(r"^\d+\s*-\s*", "", name).strip()


def already_imported(pdf_path: Path) -> bool:
    return Document.query.filter(
        Document.source_pdf.like(f"%{pdf_path.name}")
    ).first() is not None


def ingest_pdf(pdf_path: Path, step_id: int, step_type_id: int | None, doc_type: str) -> dict | None:
    if already_imported(pdf_path):
        print(f"    [skip] {pdf_path.name}")
        return None

    print(f"    [read] {pdf_path.name}")
    try:
        extracted = extract_from_pdf(str(pdf_path))
    except Exception as e:
        print(f"    [err]  {pdf_path.name}: {e}")
        return None

    meta     = extracted["metadata"]
    sections = extracted["sections"]
    content  = sections_to_markdown(sections) or extracted.get("raw_text", "")

    doc = create_document(
        title              = extracted["title"],
        content            = content,
        process_area       = extracted.get("process_area", ""),
        tags               = extracted.get("tags", []),
        step_id            = step_id,
        step_type_id       = step_type_id,
        doc_type           = doc_type,
        coral_name         = meta.get("coral_name"),
        location           = meta.get("location"),
        category           = meta.get("category"),
        contact            = meta.get("contact"),
        last_revision      = meta.get("last_revision"),
        sop_version        = meta.get("sop_version"),
        author             = meta.get("author"),
        structured_content = json.dumps(sections),
        source_pdf         = str(pdf_path),
    )
    # Extract and store images
    try:
        imgs = extract_images(str(pdf_path), doc["id"])
        for img in imgs:
            db.session.add(DocumentImage(
                document_id  = doc["id"],
                filename     = img["filename"],
                page_number  = img["page_number"],
                page_total   = img["page_total"],
                position_y   = img["position_y"],
                doc_position = img["doc_position"],
                section_name = img["section_name"],
                width        = img["width"],
                height       = img["height"],
            ))
        db.session.commit()
        if imgs:
            print(f"           {len(imgs)} image(s) extracted")
    except Exception as e:
        print(f"    [warn] image extraction failed: {e}")

    print(f"    [ok]   {doc['title']} (id={doc['id']})")
    return doc


def iter_pdfs(data_root: Path):
    """Yield (step_name, step_type_name, doc_type, file_path) for every PDF."""
    for step_dir in sorted(data_root.iterdir()):
        if not step_dir.is_dir():
            continue
        step_name = strip_number_prefix(step_dir.name)

        for level2 in sorted(step_dir.iterdir()):
            if not level2.is_dir():
                continue

            if level2.name in DOC_TYPE_DIRS:
                # Files sit directly under the step — use step name as the type
                doc_type = DOC_TYPE_MAP[level2.name]
                for f in sorted(level2.iterdir()):
                    if f.is_file() and f.suffix.lower() == ".pdf":
                        yield step_name, step_name, doc_type, f
            else:
                # level2 is a distinct StepType directory
                step_type_name = level2.name
                for level3 in sorted(level2.iterdir()):
                    if not level3.is_dir() or level3.name not in DOC_TYPE_DIRS:
                        continue
                    doc_type = DOC_TYPE_MAP[level3.name]
                    for f in sorted(level3.iterdir()):
                        if f.is_file() and f.suffix.lower() == ".pdf":
                            yield step_name, step_type_name, doc_type, f


def _ensure_schema(app):
    """Drop and recreate tables when the schema is out of date."""
    from sqlalchemy import text
    with app.app_context():
        try:
            db.session.execute(text("SELECT step_id FROM documents LIMIT 1"))
        except Exception:
            print("Schema out of date — recreating tables (all data re-imported from PDFs)…\n")
            db.drop_all()
            db.create_all()


def run(dry_run: bool = False):
    if not DATA_ROOT.exists():
        print(f"ERROR: data folder not found: {DATA_ROOT}")
        sys.exit(1)

    app = create_app()
    if not dry_run:
        _ensure_schema(app)

    with app.app_context():
        imported = skipped = 0

        for step_name, step_type_name, doc_type, fpath in iter_pdfs(DATA_ROOT):
            label = f"[{step_name}] / [{step_type_name or '—'}] / {doc_type}"
            print(f"\n{label}")

            if dry_run:
                print(f"    would import: {fpath.name}")
                continue

            step      = get_or_create_step(step_name)
            step_type = get_or_create_step_type(step, step_type_name)

            result = ingest_pdf(
                fpath,
                step_id      = step.id,
                step_type_id = step_type.id,
                doc_type     = doc_type,
            )
            if result:
                imported += 1
            else:
                skipped += 1

        if not dry_run:
            print(f"\nDone — {imported} imported, {skipped} skipped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be imported without touching the database")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
