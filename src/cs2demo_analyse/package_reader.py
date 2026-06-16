from __future__ import annotations

import bz2
import gzip
import shutil
import struct
import zlib
import zipfile
from pathlib import Path

from .io_utils import ensure_dir


class DemoPackageError(RuntimeError):
    pass


def detect_package_kind(path: Path) -> str:
    head = path.read_bytes()[:16]
    if head.startswith(b"PK\x03\x04"):
        return "zip"
    if head.startswith(b"\x1f\x8b"):
        return "gzip"
    if head.startswith(b"BZh"):
        return "bzip2"
    if head.startswith(b"PBDEMS") or head.startswith(b"HL2DEMO"):
        return "dem"
    return "unknown"


def extract_single_demo(package_path: Path, destination_dir: Path) -> Path:
    ensure_dir(destination_dir)
    kind = detect_package_kind(package_path)
    if kind == "dem":
        out = destination_dir / f"{package_path.stem}.dem"
        shutil.copyfile(package_path, out)
        return out
    if kind == "gzip":
        out = destination_dir / package_path.with_suffix("").name
        if out.suffix.lower() != ".dem":
            out = out.with_suffix(".dem")
        with gzip.open(package_path, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return out
    if kind == "bzip2":
        out = destination_dir / package_path.with_suffix("").name
        if out.suffix.lower() != ".dem":
            out = out.with_suffix(".dem")
        with bz2.open(package_path, "rb") as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return out
    if kind == "zip":
        try:
            return _extract_zipfile(package_path, destination_dir)
        except zipfile.BadZipFile:
            return _extract_first_zip_local_file(package_path, destination_dir)
    raise DemoPackageError(f"Unsupported demo package format for {package_path}")


def _extract_zipfile(package_path: Path, destination_dir: Path) -> Path:
    with zipfile.ZipFile(package_path) as archive:
        infos = [
            info for info in archive.infolist()
            if not info.is_dir() and Path(info.filename).suffix.lower() == ".dem"
        ]
        if len(infos) != 1:
            raise DemoPackageError(f"Expected exactly one .dem in {package_path}, found {len(infos)}")
        info = infos[0]
        out = destination_dir / Path(info.filename).name
        with archive.open(info) as src, out.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return out


def _extract_first_zip_local_file(package_path: Path, destination_dir: Path) -> Path:
    data = package_path.read_bytes()
    if not data.startswith(b"PK\x03\x04"):
        raise DemoPackageError(f"Not a local-header zip stream: {package_path}")
    if len(data) < 30:
        raise DemoPackageError(f"Truncated zip local header: {package_path}")

    (
        signature,
        _version,
        flags,
        method,
        _mtime,
        _mdate,
        _crc,
        compressed_size,
        uncompressed_size,
        name_len,
        extra_len,
    ) = struct.unpack_from("<IHHHHHIIIHH", data, 0)
    if signature != 0x04034B50:
        raise DemoPackageError(f"Invalid zip signature: {package_path}")
    if flags & 0x08:
        raise DemoPackageError(
            f"Zip stream uses a data descriptor and cannot be safely extracted without central directory: {package_path}"
        )
    name_start = 30
    name_end = name_start + name_len
    payload_start = name_end + extra_len
    name = data[name_start:name_end].decode("utf-8", errors="replace")
    if Path(name).suffix.lower() != ".dem":
        raise DemoPackageError(f"Zip package first file is not a .dem: {name}")
    payload_end = min(payload_start + compressed_size, len(data))
    payload = data[payload_start:payload_end]
    if method == 0:
        content = payload
    elif method == 8:
        decompressor = zlib.decompressobj(-15)
        content = decompressor.decompress(payload)
        if decompressor.unused_data:
            content = content[: len(content)]
    else:
        raise DemoPackageError(f"Unsupported zip compression method {method}: {package_path}")
    if uncompressed_size and len(content) > uncompressed_size:
        raise DemoPackageError(f"Extracted size mismatch for {package_path}")
    out = destination_dir / Path(name).name
    out.write_bytes(content)
    return out
