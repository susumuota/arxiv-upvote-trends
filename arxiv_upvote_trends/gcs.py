# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import io
import logging
import tarfile
from pathlib import Path

from google.cloud import storage

logger = logging.getLogger(__name__)


def restore_dir(bucket_name: str, blob_name: str, local_dir: str) -> None:
    """Restore a local directory from a GCS tarball.

    If the blob does not exist (first run), this is a no-op.
    """
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if not blob.exists():
        logger.info("No archive found at gs://%s/%s. Skipping download.", bucket_name, blob_name)
        return

    buf = io.BytesIO()
    blob.download_to_file(buf)
    buf.seek(0)

    with tarfile.open(fileobj=buf, mode="r:gz") as tar:
        tar.extractall(path=local_dir, filter="data")

    logger.info("Restored gs://%s/%s to %s", bucket_name, blob_name, local_dir)


def save_dir(bucket_name: str, blob_name: str, local_dir: str) -> None:
    """Upload a local directory to GCS as a tarball.

    If local_dir does not exist, this is a no-op.
    """
    local_path = Path(local_dir)
    if not local_path.exists():
        logger.info("Directory %s does not exist. Skipping upload.", local_dir)
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

    logger.info("Uploaded %s to gs://%s/%s", local_dir, bucket_name, blob_name)
