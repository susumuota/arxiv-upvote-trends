# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

import pytest

from arxiv_upvote_trends.pdf import capture_arxiv_first_page


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    mock_image = MagicMock()
    mock_convert.return_value = [mock_image]

    output_path = str(tmp_path / "page.png")
    result = capture_arxiv_first_page("2603.10165", output_path)

    assert result == output_path
    mock_get.assert_called_once()
    assert "2603.10165" in mock_get.call_args[0][0]
    mock_get.return_value.raise_for_status.assert_called_once()
    mock_convert.assert_called_once_with(b"%PDF-fake", dpi=200, first_page=1, last_page=1)
    mock_image.save.assert_called_once_with(output_path, "PNG")


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_custom_dpi(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    mock_convert.return_value = [MagicMock()]

    output_path = str(tmp_path / "page.png")
    capture_arxiv_first_page("2603.10165", output_path, dpi=300)

    mock_convert.assert_called_once_with(b"%PDF-fake", dpi=300, first_page=1, last_page=1)


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_custom_timeout(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    mock_convert.return_value = [MagicMock()]

    output_path = str(tmp_path / "page.png")
    capture_arxiv_first_page("2603.10165", output_path, timeout=60)

    mock_get.assert_called_once()
    assert mock_get.call_args[1]["timeout"] == 60


@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_raises_on_http_error(mock_get, tmp_path):
    mock_get.return_value = MagicMock()
    mock_get.return_value.raise_for_status.side_effect = Exception("404 Not Found")

    output_path = str(tmp_path / "page.png")
    with pytest.raises(Exception, match="404 Not Found"):
        capture_arxiv_first_page("0000.00000", output_path)
