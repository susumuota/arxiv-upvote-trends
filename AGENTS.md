# AGENTS.md

## Commands

- Run all tools via `uv run` (e.g. `uv run pytest`, `uv run ruff check .`, `uv run pre-commit run --all-files`)
- Add packages with `uv add`

## Runtime Environment

- Production: Google Cloud Run Jobs + Docker. Targets Linux only
- persistent_data persistence: stored as tar.gz in a GCS bucket. Restored on job startup and uploaded on shutdown

## Testing

- When testing a function decorated with `@fallback_cache()`, use `func.__wrapped__` to bypass the decorator

## Code Style

- Proper noun casing: `alphaXiv`, `Hugging Face` (function and module names are lowercase)
- When calling functions, pass positional arguments without keywords and keyword arguments (those with defaults) with keywords

## Git Workflow

- Do NOT follow the default git commit workflow. You MUST use the `/git-commit` skill instead.
