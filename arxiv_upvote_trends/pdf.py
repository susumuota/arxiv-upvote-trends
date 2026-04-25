# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging

import requests
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/146.0.0.0 Safari/537.36"
)


def capture_arxiv_first_page(arxiv_id: str, output_path: str, dpi: int = 200, timeout: float = 30) -> str:
    """Render the first page of an arXiv PDF to a PNG file.

    Higher DPI improves text sharpness at the cost of slower conversion and larger output.
    """
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    referer = f"https://arxiv.org/abs/{arxiv_id}"
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT, "Referer": referer}, timeout=timeout)
    resp.raise_for_status()
    images = convert_from_bytes(resp.content, dpi=dpi, first_page=1, last_page=1)
    images[0].save(output_path, "PNG")
    logger.info("Saved first page of %s to %s", arxiv_id, output_path)
    return output_path
