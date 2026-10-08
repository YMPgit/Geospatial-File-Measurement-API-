"""Phase-1 upload validation helpers (reject before any DB record exists)."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from app.core.exceptions import (
    FileTooLargeError,
    InvalidArchiveError,
    UnsupportedFileTypeError,
)

ALLOWED_EXTENSIONS = (".kml", ".zip")
MAX_ZIP_UNCOMPRESSED_MULTIPLIER = 20
_CHUNK_SIZE = 1024 * 1024
_MAX_FILENAME_LEN = 255


def sanitize_filename(filename: str | None) -> str:
    """Strip directory components and unsafe characters from a client filename."""
    if not filename:
        raise UnsupportedFileTypeError("No filename was provided with the upload.")
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable() and ch not in '<>:"|?*')
    name = name.strip(" .")
    if not name:
        raise UnsupportedFileTypeError("The provided filename is invalid.")
    if len(name) > _MAX_FILENAME_LEN:
        suffix = Path(name).suffix
        stem = Path(name).stem[: _MAX_FILENAME_LEN - len(suffix)]
        name = stem + suffix
    return name


def allowed_extension(filename: str) -> str:
    """Return the lowercased extension, rejecting unsupported formats with 400."""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(ALLOWED_EXTENSIONS)
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension or filename}'. Allowed: {allowed}"
        )
    return extension


def save_upload(stream: BinaryIO, dest: Path, max_bytes: int) -> int:
    """Stream an upload to ``dest`` while enforcing the byte-size limit.

    Raises ``FileTooLargeError`` (413) as soon as the limit is exceeded and
    removes the partial file in every failure path.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dest.open("wb") as handle:
            while True:
                chunk = stream.read(_CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise FileTooLargeError(
                        f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit."
                    )
                handle.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise InvalidArchiveError("The uploaded file is empty.")
    return written


def validate_zip_safety(zf: zipfile.ZipFile, max_total_bytes: int) -> list[zipfile.ZipInfo]:
    """Reject unsafe or oversized ZIP members (traversal, links, bombs)."""
    infos = [info for info in zf.infolist() if not info.is_dir()]
    if not infos:
        raise InvalidArchiveError("The ZIP archive contains no files.")

    total_uncompressed = 0
    for info in infos:
        name = info.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if name.startswith("/") or path.is_absolute() or (len(name) > 1 and name[1] == ":"):
            raise InvalidArchiveError(f"ZIP entry uses an absolute path: {info.filename}")
        if ".." in path.parts:
            raise InvalidArchiveError(f"ZIP entry escapes the archive root: {info.filename}")
        mode = info.external_attr >> 16
        if mode and stat.S_ISLNK(mode):
            raise InvalidArchiveError(f"ZIP entry is a symbolic link: {info.filename}")
        total_uncompressed += info.file_size

    if total_uncompressed > max_total_bytes:
        limit_mb = max_total_bytes // (1024 * 1024)
        raise InvalidArchiveError(
            f"ZIP archive expands beyond the {limit_mb} MB uncompressed limit."
        )
    return infos
