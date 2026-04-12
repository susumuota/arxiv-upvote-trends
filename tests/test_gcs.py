# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import io
import tarfile
from unittest.mock import MagicMock, patch

from arxiv_upvote_trends import restore_dir, save_dir


@patch("arxiv_upvote_trends.gcs.storage.Client")
def test_restore_dir_extracts_tarball(mock_client_cls, tmp_path):
    local_dir = tmp_path / "data"

    # Build a tar.gz in memory containing a single file
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        data = b"cached-data"
        info = tarfile.TarInfo(name="result.txt")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    tarball_bytes = buf.getvalue()

    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_to_file.side_effect = lambda f: f.write(tarball_bytes)

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client_cls.return_value.bucket.return_value = mock_bucket

    restore_dir("my-bucket", "data.tar.gz", str(local_dir))

    assert (local_dir / "result.txt").read_text() == "cached-data"


@patch("arxiv_upvote_trends.gcs.storage.Client")
def test_restore_dir_noop_when_blob_missing(mock_client_cls, tmp_path):
    local_dir = tmp_path / "data"

    mock_blob = MagicMock()
    mock_blob.exists.return_value = False

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client_cls.return_value.bucket.return_value = mock_bucket

    restore_dir("my-bucket", "data.tar.gz", str(local_dir))

    assert not local_dir.exists()


@patch("arxiv_upvote_trends.gcs.storage.Client")
def test_save_dir_creates_tarball(mock_client_cls, tmp_path):
    local_dir = tmp_path / "data"
    local_dir.mkdir()
    (local_dir / "result.txt").write_text("cached-data")

    uploaded = io.BytesIO()

    mock_blob = MagicMock()
    mock_blob.upload_from_file.side_effect = lambda f: uploaded.write(f.read())

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client_cls.return_value.bucket.return_value = mock_bucket

    save_dir("my-bucket", "data.tar.gz", str(local_dir))

    mock_blob.upload_from_file.assert_called_once()

    # Verify the uploaded tarball contains the file
    uploaded.seek(0)
    with tarfile.open(fileobj=uploaded, mode="r:gz") as tar:
        names = tar.getnames()
        assert "result.txt" in names


@patch("arxiv_upvote_trends.gcs.storage.Client")
def test_save_dir_noop_when_dir_missing(mock_client_cls, tmp_path):
    local_dir = tmp_path / "nonexistent"

    save_dir("my-bucket", "data.tar.gz", str(local_dir))

    mock_client_cls.return_value.bucket.return_value.blob.return_value.upload_from_file.assert_not_called()
