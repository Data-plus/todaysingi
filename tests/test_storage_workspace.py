import hashlib
from pathlib import Path

import pytest

from worker.storage_workspace import (
    StorageWorkspace,
    WorkspaceError,
    safe_storage_path,
)


def test_safe_storage_path_is_namespaced_by_product_and_job():
    assert safe_storage_path(4, "job-abc_123", "final.mp4") == (
        "products/4/jobs/job-abc_123/final.mp4"
    )


@pytest.mark.parametrize("filename", [
    "../secret.mp4", "subdir/file.mp4", r"subdir\file.mp4", "C:/secret.mp4",
    ".env", "movie.exe", "", "a" * 130 + ".mp4",
])
def test_safe_storage_path_rejects_traversal_and_unsupported_files(filename):
    with pytest.raises(WorkspaceError):
        safe_storage_path(1, "job-1", filename)


class FakeStorageClient:
    def __init__(self, download_bytes=b"input"):
        self.download_bytes = download_bytes
        self.uploads = []

    def download_storage_file(self, bucket, storage_path, destination):
        Path(destination).write_bytes(self.download_bytes)

    def upload_pipeline_asset(self, local_path, row):
        self.uploads.append((Path(local_path).read_bytes(), row))
        return row


def test_workspace_verifies_download_and_registers_output_then_cleans_temp(tmp_path):
    payload = b"source-video"
    client = FakeStorageClient(payload)
    checksum = hashlib.sha256(payload).hexdigest()

    with StorageWorkspace(client, 4, "job-4", temp_root=tmp_path) as workspace:
        root = workspace.root
        source = workspace.download_input({
            "bucket_id": "pipeline-assets",
            "storage_path": "products/4/jobs/source/raw.mp4",
            "checksum_sha256": checksum,
        }, "raw.mp4")
        assert source.read_bytes() == payload
        output = workspace.output_path("script.json")
        output.write_text('{"hook":"신기하죠"}', encoding="utf-8")
        row = workspace.register_output(output, kind="script", retention_class="keep")
        assert row["storage_path"] == "products/4/jobs/job-4/script.json"
        assert row["bucket_id"] == "pipeline-assets"
        assert row["bytes"] == output.stat().st_size
        assert row["checksum_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
        assert client.uploads[0][1] == row

    assert not root.exists()


def test_workspace_rejects_a_download_with_wrong_checksum(tmp_path):
    client = FakeStorageClient(b"tampered")
    with StorageWorkspace(client, 2, "job-2", temp_root=tmp_path) as workspace:
        with pytest.raises(WorkspaceError, match="checksum"):
            workspace.download_input({
                "bucket_id": "pipeline-assets",
                "storage_path": "products/2/jobs/source/raw.mp4",
                "checksum_sha256": "0" * 64,
            }, "raw.mp4")
