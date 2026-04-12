# Copyright (c) 2026 Susumu Ota
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock, patch

from arxiv_upvote_trends import upload_papers


@patch("arxiv_upvote_trends.dataset.HfApi")
def test_upload_papers(mock_hf_api_cls):
    mock_api = MagicMock()
    mock_hf_api_cls.return_value = mock_api

    papers = [{"id": "1", "title": "Paper 1"}, {"id": "2", "title": "Paper 2"}]
    url = upload_papers(papers, "user/test-repo", "raw/alphaxiv.jsonl")

    mock_api.upload_file.assert_called_once()
    upload_kwargs = mock_api.upload_file.call_args
    assert upload_kwargs.kwargs["path_in_repo"] == "raw/alphaxiv.jsonl"
    assert upload_kwargs.kwargs["repo_id"] == "user/test-repo"
    assert upload_kwargs.kwargs["repo_type"] == "dataset"
    assert url == "https://huggingface.co/datasets/user/test-repo"
