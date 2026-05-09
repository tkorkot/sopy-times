"""
Sync your Google Drive data folder into the SOP Hub database.

Usage:
    python scripts/sync_drive.py            # inspect + sync everything
    python scripts/sync_drive.py --inspect  # list Drive contents, don't download

What it does:
    1. Connects to your Drive folder (set GOOGLE_DRIVE_FOLDER_ID in .env)
    2. Inspects the folder to list all files and their types
    3. Downloads all files to the local directory (preserves Drive folder structure)
    4. Finds all PDFs in the downloaded files
    5. For each PDF  → extracts content via pdf_service → inserts into database
    6. Skips files already in the database (matched by source filename)
"""

import argparse
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import json
from app import create_app
from database.db import db
from database.models import Document
from services import drive_service
from services.pdf_service import extract_from_pdf, sections_to_markdown
from services.document_service import create_document

DOWNLOAD_DIR = Path(os.getenv("DRIVE_DOWNLOAD_DIR", "data"))


def already_imported(filename: str) -> bool:
    """Check if a file with this source name is already in the database."""
    return Document.query.filter(
        Document.source_pdf.like(f"%{filename}")
    ).first() is not None


def ingest_pdf(pdf_path: Path) -> dict | None:
    """Parse a PDF and insert it into the database. Returns the doc dict or None if skipped."""
    if already_imported(pdf_path.name):
        print(f"  [skip] {pdf_path.name} — already in database")
        return None

    print(f"  [pdf]  {pdf_path.name} — extracting…")
    try:
        extracted = extract_from_pdf(str(pdf_path))
    except Exception as e:
        print(f"  [err]  Failed to parse {pdf_path.name}: {e}")
        return None

    meta     = extracted["metadata"]
    sections = extracted["sections"]
    content  = sections_to_markdown(sections) if sections else extracted["raw_text"]

    doc = create_document(
        title              = extracted["title"],
        content            = content,
        process_area       = extracted["process_area"],
        tags               = extracted["tags"],
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
    print(f"  [ok]   Imported: {doc['title']} (id={doc['id']})")
    return doc


def run(inspect_only=False):
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        print("ERROR: Set GOOGLE_DRIVE_FOLDER_ID in your .env file.")
        sys.exit(1)

    # ── Step 1: inspect Drive folder ──────────────────────────────
    print(f"\nConnecting to Drive folder: {folder_id}")
    summary = drive_service.inspect_folder(folder_id)
    print(f"Found {summary['total']} files: {summary['by_type']}")

    if inspect_only:
        print("\nFiles:")
        for f in summary["files"]:
            print(f"  [{f['type']:5s}] {f['name']}")
        return

    # ── Step 2: download (preserves Drive folder structure) ───────
    print(f"\nDownloading to {DOWNLOAD_DIR}/…")
    downloaded = drive_service.download_folder(DOWNLOAD_DIR, folder_id)
    print(f"Downloaded {len(downloaded)} file(s).")

    # ── Step 3: ingest all PDFs found anywhere in the tree ────────
    app = create_app()
    with app.app_context():
        imported = 0
        pdfs = [p for p in downloaded if p.suffix.lower() == ".pdf"]
        print(f"Found {len(pdfs)} PDF(s) to ingest.")
        for path in pdfs:
            doc = ingest_pdf(path)
            if doc:
                imported += 1

        print(f"\nDone — {imported} new SOP(s) added to database.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync Google Drive folder into SOP Hub")
    parser.add_argument("--inspect", action="store_true", help="List Drive contents without downloading")
    args = parser.parse_args()

    run(inspect_only=args.inspect)
