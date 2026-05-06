# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

import logging
from pathlib import Path

import requests
from pdf2image import convert_from_bytes

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/146.0.0.0 Safari/537.36"
)


def capture_arxiv_first_page(
    arxiv_id: str,
    output_path: str,
    dpi: int = 160,
    timeout: float = 30,
    max_output_bytes: int | None = None,
    min_dpi: int = 80,
    dpi_step: int = 20,
) -> str:
    """Render the first page of an arXiv PDF to a PNG file.

    Higher DPI improves text sharpness at the cost of slower conversion and larger output.
    """
    if min_dpi > dpi:
        raise ValueError("min_dpi must be less than or equal to dpi")
    if dpi_step <= 0:
        raise ValueError("dpi_step must be positive")

    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    referer = f"https://arxiv.org/abs/{arxiv_id}"
    resp = requests.get(url, headers={"User-Agent": _USER_AGENT, "Referer": referer}, timeout=timeout)
    resp.raise_for_status()

    output = Path(output_path)
    current_dpi = dpi
    last_size = 0
    while True:
        images = convert_from_bytes(resp.content, dpi=current_dpi, first_page=1, last_page=1)
        images[0].save(output, "PNG", optimize=True)
        last_size = output.stat().st_size
        if max_output_bytes is None or last_size <= max_output_bytes:
            logger.info(
                "Saved first page of %s to %s at dpi=%s size=%s bytes",
                arxiv_id,
                output_path,
                current_dpi,
                last_size,
            )
            return output_path
        if current_dpi <= min_dpi:
            break

        next_dpi = max(min_dpi, current_dpi - dpi_step)
        logger.info(
            "First page of %s is %s bytes at dpi=%s, exceeding max_output_bytes=%s; retrying at dpi=%s",
            arxiv_id,
            last_size,
            current_dpi,
            max_output_bytes,
            next_dpi,
        )
        current_dpi = next_dpi

    raise ValueError(f"First page image for {arxiv_id} is {last_size} bytes at min_dpi={min_dpi}")
