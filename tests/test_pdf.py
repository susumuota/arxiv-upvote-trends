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
    mock_image.save.side_effect = lambda path, *_args, **_kwargs: path.write_bytes(b"x" * 9)
    mock_convert.return_value = [mock_image]

    output_path = str(tmp_path / "page.png")
    result = capture_arxiv_first_page("2603.10165", output_path)

    assert result == output_path
    mock_get.assert_called_once()
    assert "2603.10165" in mock_get.call_args[0][0]
    mock_get.return_value.raise_for_status.assert_called_once()
    mock_convert.assert_called_once_with(b"%PDF-fake", dpi=160, first_page=1, last_page=1)
    mock_image.save.assert_called_once_with(tmp_path / "page.png", "PNG", optimize=True)


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_custom_dpi(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    mock_image = MagicMock()
    mock_image.save.side_effect = lambda path, *_args, **_kwargs: path.write_bytes(b"x" * 9)
    mock_convert.return_value = [mock_image]

    output_path = str(tmp_path / "page.png")
    capture_arxiv_first_page("2603.10165", output_path, dpi=300)

    mock_convert.assert_called_once_with(b"%PDF-fake", dpi=300, first_page=1, last_page=1)


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_custom_timeout(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    mock_image = MagicMock()
    mock_image.save.side_effect = lambda path, *_args, **_kwargs: path.write_bytes(b"x" * 9)
    mock_convert.return_value = [mock_image]

    output_path = str(tmp_path / "page.png")
    capture_arxiv_first_page("2603.10165", output_path, timeout=60)

    mock_get.assert_called_once()
    assert mock_get.call_args[1]["timeout"] == 60


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_retries_with_lower_dpi_when_too_large(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    output_path = str(tmp_path / "page.png")

    def save_first(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 11)

    def save_second(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 9)

    first_image = MagicMock()
    first_image.save.side_effect = save_first
    second_image = MagicMock()
    second_image.save.side_effect = save_second
    mock_convert.side_effect = [[first_image], [second_image]]

    result = capture_arxiv_first_page("2603.10165", output_path, max_output_bytes=10, min_dpi=140)

    assert result == output_path
    assert [call.kwargs["dpi"] for call in mock_convert.call_args_list] == [160, 140]


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_logs_file_size_and_retry(mock_get, mock_convert, tmp_path, caplog):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    output_path = str(tmp_path / "page.png")

    def save_first(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 11)

    def save_second(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 9)

    first_image = MagicMock()
    first_image.save.side_effect = save_first
    second_image = MagicMock()
    second_image.save.side_effect = save_second
    mock_convert.side_effect = [[first_image], [second_image]]

    with caplog.at_level("INFO"):
        capture_arxiv_first_page("2603.10165", output_path, max_output_bytes=10, min_dpi=140)

    assert "exceeding max_output_bytes=10; retrying at dpi=140" in caplog.text
    assert "size=9 bytes" in caplog.text


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_defaults_to_retry_down_to_80_dpi(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    output_path = str(tmp_path / "page.png")

    def save_large(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 11)

    mock_image = MagicMock()
    mock_image.save.side_effect = save_large
    mock_convert.return_value = [mock_image]

    with pytest.raises(ValueError, match="min_dpi=80"):
        capture_arxiv_first_page("2603.10165", output_path, max_output_bytes=10)

    assert [call.kwargs["dpi"] for call in mock_convert.call_args_list] == [160, 140, 120, 100, 80]


@patch("arxiv_upvote_trends.pdf.convert_from_bytes")
@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_raises_when_min_dpi_is_still_too_large(mock_get, mock_convert, tmp_path):
    mock_get.return_value = MagicMock(content=b"%PDF-fake")
    output_path = str(tmp_path / "page.png")

    def save_large(path, *_args, **_kwargs):
        path.write_bytes(b"x" * 11)

    mock_image = MagicMock()
    mock_image.save.side_effect = save_large
    mock_convert.return_value = [mock_image]

    with pytest.raises(ValueError, match="min_dpi=160"):
        capture_arxiv_first_page("2603.10165", output_path, max_output_bytes=10, min_dpi=160)


@patch("arxiv_upvote_trends.pdf.requests.get")
def test_capture_arxiv_first_page_raises_on_http_error(mock_get, tmp_path):
    mock_get.return_value = MagicMock()
    mock_get.return_value.raise_for_status.side_effect = Exception("404 Not Found")

    output_path = str(tmp_path / "page.png")
    with pytest.raises(Exception, match="404 Not Found"):
        capture_arxiv_first_page("0000.00000", output_path)
