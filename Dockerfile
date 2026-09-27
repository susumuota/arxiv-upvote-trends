FROM ghcr.io/astral-sh/uv:0.12.19 AS uv

FROM python:3.14.6-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    libharfbuzz-subset0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY arxiv_upvote_trends/ arxiv_upvote_trends/
COPY main.py .

CMD ["uv", "run", "--frozen", "--no-dev", "python", "main.py"]
