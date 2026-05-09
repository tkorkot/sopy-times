"""
Google Drive service — uses gdown (no OAuth setup required).

Requirements:
    - Share your Drive folder with "Anyone with the link" (view only)
    - Set GOOGLE_DRIVE_FOLDER_ID in .env

That's it. No Google Cloud Console, no credentials file.
"""

import os
from pathlib import Path
import gdown


def get_folder_id() -> str:
    folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        raise ValueError("GOOGLE_DRIVE_FOLDER_ID is not set in your .env file.")
    return folder_id


def inspect_folder(folder_id: str | None = None) -> dict:
    """
    List what is currently in the Drive folder without downloading anything.

    Returns a summary dict:
        {
            "folder_id": str,
            "total":     int,
            "by_type":   {"pdf": int, "image": int, "other": int},
            "files":     [{"name": str, "id": str, "type": str}, ...]
        }
    """
    folder_id = folder_id or get_folder_id()
    url = f"https://drive.google.com/drive/folders/{folder_id}"

    # gdown.download_folder with skip_download=True just fetches the file list
    files_info = gdown.download_folder(url, skip_download=True, quiet=True) or []

    classified = []
    by_type: dict[str, int] = {"pdf": 0, "image": 0, "other": 0}

    for file in files_info:
        if isinstance(file, str):
            path_str = file
        else:
            path_str = getattr(file, "path", None) \
                    or getattr(file, "local_path", None) \
                    or str(file)

        name = Path(path_str).name
        ext = Path(path_str).suffix.lower()

        classified.append({
            "name": name,
            "id": file.id,
            "type": ext if ext in [".pdf", ".jpg", ".jpeg", ".png"] else "other",
        })

    return {
        "folder_id": folder_id,
        "total":     len(classified),
        "by_type":   by_type,
        "files":     classified,
    }


def download_folder(dest_dir: str | Path, folder_id: str | None = None) -> list[Path]:
    """
    Download all files from the Drive folder into dest_dir.

    Returns a list of local Paths for every downloaded file.
    """
    folder_id = folder_id or get_folder_id()
    dest      = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    url = f"https://drive.google.com/drive/folders/{folder_id}"
    downloaded = gdown.download_folder(url, output=str(dest), quiet=False) or []
    return [Path(p) for p in downloaded]


def download_file(file_id: str, dest_path: str | Path) -> Path:
    """Download a single Drive file by its file ID."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://drive.google.com/uc?id={file_id}"
    gdown.download(url, str(dest), quiet=False)
    return dest
