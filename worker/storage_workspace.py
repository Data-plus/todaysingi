"""Cloud Worker의 임시 작업 디렉터리와 Supabase Storage 경계를 관리한다."""
from __future__ import annotations

import hashlib
import mimetypes
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
ALLOWED_EXTENSIONS = {
    ".mp4", ".jpg", ".jpeg", ".png", ".webp",
    ".mp3", ".wav", ".txt", ".json", ".srt",
}
MIME_OVERRIDES = {
    ".json": "application/json",
    ".srt": "application/x-subrip",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}
ASSET_KINDS = {
    "thumbnail", "raw_video", "muted_video", "frame", "script", "voice",
    "subtitle", "final_video", "cover_candidate", "reel_cover", "caption",
    "log", "metrics",
}
RETENTION_CLASSES = {"ephemeral", "review", "keep"}


class WorkspaceError(ValueError):
    pass


def _safe_filename(filename: str) -> str:
    value = str(filename or "")
    if not SAFE_NAME.fullmatch(value) or ".." in value:
        raise WorkspaceError("허용되지 않는 filename입니다")
    if Path(value).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise WorkspaceError("허용되지 않는 파일 확장자입니다")
    return value


def safe_storage_path(product_id: int, job_id: str, filename: str) -> str:
    if not isinstance(product_id, int) or isinstance(product_id, bool) or product_id < 1:
        raise WorkspaceError("product_id는 일 이상의 정수여야 합니다")
    if not SAFE_JOB_ID.fullmatch(str(job_id or "")):
        raise WorkspaceError("job_id 형식이 올바르지 않습니다")
    return f"products/{product_id}/jobs/{job_id}/{_safe_filename(filename)}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_remote_path(value: str) -> str:
    path = PurePosixPath(str(value or ""))
    if path.is_absolute() or not path.parts or ".." in path.parts or "." in path.parts:
        raise WorkspaceError("Storage path가 올바르지 않습니다")
    return path.as_posix()


class StorageWorkspace:
    def __init__(self, client, product_id: int, job_id: str, *, temp_root: Path | None = None):
        safe_storage_path(product_id, job_id, "probe.txt")
        self.client = client
        self.product_id = product_id
        self.job_id = job_id
        self.temp_root = Path(temp_root) if temp_root is not None else None
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self.root: Path | None = None
        self.inputs: Path | None = None
        self.outputs: Path | None = None

    def __enter__(self):
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True)
        self._temporary = tempfile.TemporaryDirectory(
            prefix=f"todaysingi-{self.product_id}-",
            dir=str(self.temp_root) if self.temp_root is not None else None,
        )
        self.root = Path(self._temporary.name)
        self.inputs = self.root / "inputs"
        self.outputs = self.root / "outputs"
        self.inputs.mkdir()
        self.outputs.mkdir()
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        if self._temporary is not None:
            self._temporary.cleanup()
        self.root = None
        self.inputs = None
        self.outputs = None

    def _active_dir(self, value: Path | None) -> Path:
        if value is None:
            raise WorkspaceError("StorageWorkspace context 안에서만 사용할 수 있습니다")
        return value

    def output_path(self, filename: str) -> Path:
        return self._active_dir(self.outputs) / _safe_filename(filename)

    def download_input(self, asset: dict[str, Any], filename: str) -> Path:
        destination = self._active_dir(self.inputs) / _safe_filename(filename)
        bucket = str(asset.get("bucket_id") or "")
        if bucket not in {"pipeline-assets", "completed-assets"}:
            raise WorkspaceError("허용되지 않는 Storage bucket입니다")
        storage_path = _safe_remote_path(str(asset.get("storage_path") or ""))
        self.client.download_storage_file(bucket, storage_path, destination)
        expected = str(asset.get("checksum_sha256") or "").lower()
        if expected and sha256_file(destination) != expected:
            destination.unlink(missing_ok=True)
            raise WorkspaceError("Storage input checksum이 일치하지 않습니다")
        return destination

    def register_output(
        self,
        local_path: Path,
        *,
        kind: str,
        retention_class: str,
        review_status: str = "pending",
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        output_root = self._active_dir(self.outputs).resolve()
        path = Path(local_path).resolve()
        try:
            path.relative_to(output_root)
        except ValueError as exc:
            raise WorkspaceError("Workspace outputs 밖의 파일은 업로드할 수 없습니다") from exc
        if not path.is_file():
            raise WorkspaceError("업로드할 산출물 파일이 없습니다")
        filename = _safe_filename(path.name)
        if kind not in ASSET_KINDS:
            raise WorkspaceError("지원하지 않는 asset kind입니다")
        if retention_class not in RETENTION_CLASSES:
            raise WorkspaceError("지원하지 않는 retention class입니다")
        extension = path.suffix.lower()
        mime_type = MIME_OVERRIDES.get(extension) or mimetypes.types_map.get(extension)
        if not mime_type:
            raise WorkspaceError("파일 MIME type을 결정할 수 없습니다")
        row = {
            "product_id": self.product_id,
            "job_id": self.job_id,
            "kind": kind,
            "bucket_id": "pipeline-assets",
            "storage_path": safe_storage_path(self.product_id, self.job_id, filename),
            "mime_type": mime_type,
            "bytes": path.stat().st_size,
            "checksum_sha256": sha256_file(path),
            "review_status": review_status,
            "retention_class": retention_class,
            "expires_at": expires_at,
            "cleanup_status": "active",
            "metadata": metadata or {},
        }
        self.client.upload_pipeline_asset(path, row)
        return row
