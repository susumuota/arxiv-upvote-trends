FROM python:3.14.4-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY arxiv_upvote_trends/ arxiv_upvote_trends/
COPY main.py .

CMD ["uv", "run", "--frozen", "--no-dev", "python", "main.py"]
