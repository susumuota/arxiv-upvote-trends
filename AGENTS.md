# AGENTS.md

## Commands

- Run all tools via `uv run` (e.g. `uv run ruff check`, `uv run ruff format`, `uv run ty check`, `uv run pytest`, etc.)
- Add packages with `uv add`

## Runtime Environment

- Production: Google Cloud Run Jobs + Docker. Targets Linux only
- persistent_data persistence: stored as tar.gz in a GCS bucket. Restored on job startup and uploaded on shutdown

## Testing

- During iterative development, run only the focused tests relevant to the changed files
- Do not manually repeat the full pytest suite when the next step is `git commit`; the pre-commit hook runs `uv run pytest` automatically
- When testing a function decorated with `@fallback_cache()`, use `func.__wrapped__` to bypass the decorator

## Code Style

- Proper noun casing: `alphaXiv`, `Hugging Face` (function and module names are lowercase)
- When calling functions, pass positional arguments without keywords and keyword arguments (those with defaults) with keywords

## Git Workflow

- When a task requires creating a commit, use the `/git-commit` skill instead of ad-hoc git commit steps.
