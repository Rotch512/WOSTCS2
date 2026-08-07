from __future__ import annotations

from pathlib import Path
import html
import re
import time

from tqdm import tqdm

from .config import REPLAYS_DATA_FOLDER_ID
from .io_utils import ensure_dir
from .sheets import _build_services


def download_file(file_id: str, destination: Path, name: str = "") -> Path:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError("google-api-python-client is required for Drive downloads.") from exc

    ensure_dir(destination.parent)
    label = name or file_id
    try:
        drive, _ = _build_services()
        request = drive.files().get_media(fileId=file_id, supportsAllDrives=True)
        temp_destination = destination.with_suffix(destination.suffix + ".part")
        if temp_destination.exists():
            temp_destination.unlink()
        with temp_destination.open("wb") as fh:
            downloader = MediaIoBaseDownload(fh, request, chunksize=32 * 1024 * 1024)
            done = False
            with tqdm(unit="B", unit_scale=True, unit_divisor=1024, desc=label, mininterval=0.5) as pbar:
                while not done:
                    status, done = downloader.next_chunk()
                    if pbar.total != status.total_size:
                        pbar.total = status.total_size
                    pbar.n = status.resumable_progress
                    pbar.refresh()
        temp_destination.replace(destination)
        return destination
    except Exception:
        return download_public_drive_file(file_id, destination, name)


def download_public_drive_file(file_id: str, destination: Path, name: str = "") -> Path:
    import requests

    ensure_dir(destination.parent)
    label = name or file_id
    last_error: Exception | None = None
    for attempt in range(1, 6):
        session = requests.Session()
        url = "https://drive.google.com/uc"
        try:
            response = session.get(url, params={"export": "download", "id": file_id}, stream=True, timeout=120)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                page = response.text
                action_match = re.search(r'<form[^>]+id="download-form"[^>]+action="([^"]+)"', page)
                action = action_match.group(1) if action_match else "https://drive.usercontent.google.com/download"
                params = {"id": file_id, "export": "download", "confirm": "t"}
                for name_key in ("uuid", "resourcekey"):
                    match = re.search(rf'name="{name_key}" value="([^"]+)"', page)
                    if match:
                        params[name_key] = match.group(1)
                response = session.get(action, params=params, stream=True, timeout=120)
                response.raise_for_status()
            desc = f"{label} (attempt {attempt})" if attempt > 1 else label
            return _stream_response_to_file(response, destination, desc)
        except requests.RequestException as exc:
            last_error = exc
            temp_destination = destination.with_suffix(destination.suffix + ".part")
            if temp_destination.exists():
                temp_destination.unlink()
            if attempt == 5:
                break
            time.sleep(min(30, 2 ** attempt))
    if last_error:
        raise last_error
    raise RuntimeError(f"Failed to download Google Drive file: {file_id}")


def _stream_response_to_file(response, destination: Path, desc: str = "") -> Path:
    temp_destination = destination.with_suffix(destination.suffix + ".part")
    if temp_destination.exists():
        temp_destination.unlink()
    total = int(response.headers.get("content-length", 0)) or None
    with temp_destination.open("wb") as fh:
        with tqdm(total=total, unit="B", unit_scale=True, unit_divisor=1024, desc=desc, mininterval=0.5) as pbar:
            for chunk in response.iter_content(chunk_size=8 * 1024 * 1024):
                if chunk:
                    fh.write(chunk)
                    pbar.update(len(chunk))
    temp_destination.replace(destination)
    return destination


def package_path_for(file_id: str, original_name: str, packages_dir: Path) -> Path:
    return packages_dir / f"{file_id}.pkg"


def list_drive_folder_files(folder_id: str = REPLAYS_DATA_FOLDER_ID) -> list[dict[str, str]]:
    drive, _ = _build_services()
    files: list[dict[str, str]] = []
    page_token = None
    while True:
        response = drive.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id,name,mimeType,modifiedTime,size,md5Checksum)",
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return sorted(files, key=lambda item: item.get("name", ""))


def list_public_drive_folder_files(folder_id: str = REPLAYS_DATA_FOLDER_ID) -> list[dict[str, str]]:
    import requests

    urls = [
        (f"https://drive.google.com/embeddedfolderview", {"id": folder_id}),
        (f"https://drive.google.com/drive/folders/{folder_id}", {"usp": "drive_link"}),
    ]
    pattern = re.compile(
        r'(?:id="entry-|data-id=")(?P<id>[A-Za-z0-9_-]{20,})".{0,5000}?'
        r'(?:<div class="flip-entry-title">|aria-label=")'
        r'(?P<name>20\d{6}_[a-z0-9]+_(?:full|subbed)_(?:win|lose|draw)_\d{1,2}_\d{1,2}\.zip)',
        re.DOTALL,
    )
    by_id: dict[str, dict[str, str]] = {}
    for url, params in urls:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        for match in pattern.finditer(response.text):
            file_id = match.group("id")
            name = html.unescape(match.group("name"))
            by_id[file_id] = {
                "id": file_id,
                "name": name,
                "mimeType": "application/x-zip-compressed",
                "modifiedTime": "",
                "size": "",
                "md5Checksum": "",
            }
    return sorted(by_id.values(), key=lambda item: item.get("name", ""))


def find_file_in_folder(name: str, folder_id: str = REPLAYS_DATA_FOLDER_ID) -> dict[str, str] | None:
    drive, _ = _build_services()
    response = drive.files().list(
        q=f"'{folder_id}' in parents and trashed = false and name = '{name}'",
        fields="files(id,name,mimeType,modifiedTime,size)",
        pageSize=10,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    files = response.get("files", [])
    return files[0] if files else None


def download_text_file(file_id: str) -> str:
    drive, _ = _build_services()
    return drive.files().get_media(fileId=file_id, supportsAllDrives=True).execute().decode("utf-8")


def upsert_text_file_in_folder(name: str, content: str, folder_id: str = REPLAYS_DATA_FOLDER_ID) -> str:
    from googleapiclient.http import MediaIoBaseUpload
    import io

    drive, _ = _build_services()
    media = MediaIoBaseUpload(io.BytesIO(content.encode("utf-8")), mimetype="application/json", resumable=False)
    existing = find_file_in_folder(name, folder_id)
    if existing:
        drive.files().update(fileId=existing["id"], media_body=media, supportsAllDrives=True).execute()
        return existing["id"]
    created = drive.files().create(
        body={"name": name, "parents": [folder_id], "mimeType": "application/json"},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return created["id"]
