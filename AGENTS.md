# AGENTS.md

This file provides guidance to coding agents when working with code in this repository.

## Project Overview

A tool to collect trending arXiv papers from the alphaXiv / Hugging Face APIs. The `fallback_cache` decorator automatically falls back to cached results when an API is unavailable.

## Commands

```bash
# Run
python main.py

# Test (all)
pytest

# Test (single file)
pytest tests/test_cache.py

# Lint
ruff check .

# Format
ruff format .

# pre-commit (run all hooks)
uv run pre-commit run --all-files

# Add package
uv add <package>
```

## Architecture

- **main.py** — Entry point. Runs the alphaXiv / Hugging Face searches
- **arxiv_upvote_trends/** — Main package
  - **alphaxiv.py** — alphaXiv API client. Fetches papers with pagination
  - **cache.py** — joblib-based cache decorator. `@fallback_cache()` wraps any function, updates the cache on success, and returns the cached result on exception. Used by the search functions in alphaxiv.py / hf.py
  - **dataset.py** — Upload to / download from Hugging Face Dataset
  - **gcs.py** — GCS synchronization. On startup, downloads and extracts a tar.gz from GCS; on shutdown, compresses and uploads the local directory
  - **hf.py** — Hugging Face Daily Papers client. Fetches papers with pagination

## Runtime Environment

- Production: Google Cloud Run Jobs + Docker (`python:3.14.3-slim`). Targets Linux only; Windows / macOS compatibility is not a concern
- fallback_cache persistence: stored as tar.gz in a GCS bucket. Restored on job startup and uploaded on shutdown

## Testing Conventions

- Mock `time.sleep` and external APIs with `unittest.mock.patch`
- When testing a function decorated with `@fallback_cache()`, use `func.__wrapped__` to bypass the decorator

## Code Style

- Use Ruff (line-length=119)
- Proper noun casing: `alphaXiv`, `Hugging Face` (function and module names are lowercase)
- When calling functions, pass positional arguments without keywords and keyword arguments (those with defaults) with keywords

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/). Keep the commit message on a single line. Examples:

- `feat: add pagination to alphaXiv client`
- `fix: handle timeout in fallback_cache`
- `ci: add GitHub Actions workflow`
- `docs: update README setup steps`
- `chore: update dependencies`

## Push

Use `git push origin main`.
