# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from arxiv_upvote_trends.arxiv import is_arxiv_id, parse_arxiv_ids


def test_is_arxiv_id_accepts_new_style_ids():
    assert is_arxiv_id("0704.0001")
    assert is_arxiv_id("1412.9999")
    assert is_arxiv_id("1501.00001")
    assert is_arxiv_id("2603.10165")
    assert is_arxiv_id("2603.10165v2")


def test_is_arxiv_id_rejects_non_arxiv_ids():
    assert not is_arxiv_id("")
    assert not is_arxiv_id("deepseek-v4")
    assert not is_arxiv_id("arXiv:2603.10165")
    assert not is_arxiv_id("https://arxiv.org/abs/2603.10165")
    assert not is_arxiv_id("alg-geom/9701001")
    assert not is_arxiv_id("hep-th/9901001")
    assert not is_arxiv_id("math.GT/0309136")
    assert not is_arxiv_id("0703.0001")
    assert not is_arxiv_id("0704.0000")
    assert not is_arxiv_id("1412.00001")
    assert not is_arxiv_id("1501.0001")
    assert not is_arxiv_id("2603.10165v0")


def test_parse_arxiv_ids_abs_url():
    assert parse_arxiv_ids("https://arxiv.org/abs/2604.12345") == ["2604.12345"]


def test_parse_arxiv_ids_pdf_url():
    assert parse_arxiv_ids("https://arxiv.org/pdf/2604.12345") == ["2604.12345"]


def test_parse_arxiv_ids_html_url():
    assert parse_arxiv_ids("https://arxiv.org/html/2604.12345") == ["2604.12345"]


def test_parse_arxiv_ids_strips_version():
    assert parse_arxiv_ids("https://arxiv.org/abs/2604.12345v2") == ["2604.12345"]


def test_parse_arxiv_ids_pdf_with_extension():
    assert parse_arxiv_ids("https://arxiv.org/pdf/2604.12345.pdf") == ["2604.12345"]


def test_parse_arxiv_ids_four_digit_id():
    assert parse_arxiv_ids("https://arxiv.org/abs/0704.0001") == ["0704.0001"]


def test_parse_arxiv_ids_non_arxiv_url():
    assert parse_arxiv_ids("https://example.com") == []


def test_parse_arxiv_ids_empty_string():
    assert parse_arxiv_ids("") == []


def test_parse_arxiv_ids_rejects_invalid_arxiv_id_in_url():
    assert parse_arxiv_ids("https://arxiv.org/abs/0703.0001") == []
    assert parse_arxiv_ids("https://arxiv.org/abs/0704.0000") == []


def test_parse_arxiv_ids_strips_invalid_version():
    assert parse_arxiv_ids("https://arxiv.org/abs/2603.10165v0") == ["2603.10165"]
