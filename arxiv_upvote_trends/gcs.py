# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import io
import logging
import tarfile
from pathlib import Path

from google.cloud import storage

logger = logging.getLogger(__name__)


def restore_dir(bucket_name: str, blob_name: str, local_dir: str) -> None:
    """Download a tarball from GCS and extract it to local_dir.

    If the blob does not exist (first run), this is a no-op.

    Args:
        bucket_name: GCS bucket name.
        blob_name: Blob name of the tar.gz archive in the bucket.
        local_dir: Local directory to extract into.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if not blob.exists():
        logger.info(f"No archive found at gs://{bucket_name}/{blob_name}. Skipping download.")
        return

    buf = io.BytesIO()
    blob.download_to_file(buf)
    buf.seek(0)

    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar.extractall(path=local_dir, filter="data")

    logger.info(f"Restored gs://{bucket_name}/{blob_name} to {local_dir}")


def save_dir(bucket_name: str, blob_name: str, local_dir: str) -> None:
    """Compress local_dir into a tarball and upload it to GCS.

    If local_dir does not exist, this is a no-op.

    Args:
        bucket_name: GCS bucket name.
        blob_name: Blob name of the tar.gz archive in the bucket.
        local_dir: Local directory to compress and upload.
    """
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.info(f"Directory {local_dir} does not exist. Skipping upload.")
        return

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for entry in local_path.iterdir():
            tar.add(entry, arcname=entry.name)
    buf.seek(0)

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.upload_from_file(buf)

    logger.info(f"Uploaded {local_dir} to gs://{bucket_name}/{blob_name}")
