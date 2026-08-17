"""يُنزّل صور ومقاطع مجلّد درايف إلى `assets/incoming/`.

يعمل بثلاث طرق حسب ما هو متاح:

1. **Colab**  — إذا كان درايف مركّبًا على `/content/drive` يُنسخ الملفّ مباشرة.
2. **حساب خدمة** — عبر `GOOGLE_APPLICATION_CREDENTIALS` (ملف JSON لحساب خدمة
   مُشارَك معه المجلّد).
3. **مجلّد محلّي** — عبر `--from <مسار>` لأي نسخة محلّية من المجلّد.

    python scripts/fetch_drive.py --folder-id 1SRGnQImHKDtJqUXEc44ev4c_1HbTtlxc
    python scripts/fetch_drive.py --from ~/Downloads/TikTokContent
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".mp4", ".mov", ".m4v"}
DEST = Path("assets/incoming")
DEFAULT_FOLDER_ID = "1SRGnQImHKDtJqUXEc44ev4c_1HbTtlxc"   # مجلّد TikTok Content


def _copy_tree(src: Path, dest: Path) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(src.rglob("*")):
        if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES:
            shutil.copy2(path, dest / path.name)
            count += 1
    return count


def from_local(source: str) -> int:
    src = Path(source).expanduser()
    if not src.is_dir():
        raise SystemExit(f"✖ ليس مجلّدًا: {src}")
    return _copy_tree(src, DEST)


def from_colab(folder_name: str = "TikTok Content") -> int:
    root = Path("/content/drive/MyDrive")
    if not root.exists():
        raise SystemExit("✖ درايف غير مركّب. نفّذ: drive.mount('/content/drive')")
    matches = [p for p in root.rglob(folder_name) if p.is_dir()]
    if not matches:
        raise SystemExit(f"✖ لم أجد مجلّد «{folder_name}» في درايف")
    return _copy_tree(matches[0], DEST)


def from_service_account(folder_id: str) -> int:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError:
        raise SystemExit(
            "✖ ينقص: pip install google-api-python-client google-auth"
        )

    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        raise SystemExit("✖ لم يُضبط GOOGLE_APPLICATION_CREDENTIALS")

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    service = build("drive", "v3", credentials=creds)
    DEST.mkdir(parents=True, exist_ok=True)

    count = 0
    page = None
    while True:
        resp = (
            service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page,
                pageSize=200,
            )
            .execute()
        )
        for meta in resp.get("files", []):
            if not meta["mimeType"].startswith(("image/", "video/")):
                continue
            target = DEST / meta["name"]
            request = service.files().get_media(fileId=meta["id"])
            with open(target, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
            print(f"  ↓ {meta['name']}")
            count += 1
        page = resp.get("nextPageToken")
        if not page:
            break
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="تنزيل وسائط أجمكان من درايف")
    ap.add_argument("--folder-id", default=DEFAULT_FOLDER_ID)
    ap.add_argument("--from", dest="source", help="مجلّد محلّي بدل درايف")
    ap.add_argument("--colab", action="store_true", help="نسخ من درايف المركّب في Colab")
    args = ap.parse_args()

    if args.source:
        n = from_local(args.source)
    elif args.colab or Path("/content/drive").exists():
        n = from_colab()
    else:
        n = from_service_account(args.folder_id)

    print(f"✔ نُقل {n} ملفًا إلى {DEST}")


if __name__ == "__main__":
    main()
