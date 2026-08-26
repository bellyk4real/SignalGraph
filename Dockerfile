FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependency layer first for build-cache reuse across source-only changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code needed at runtime: the agent API, the demo script,
# fixtures/registry data, and migrations (so `uv run alembic upgrade head`
# can be run from the image too, e.g. as a pre-deploy job).
COPY src/ src/
COPY demo/ demo/
COPY data/ data/
COPY infra/ infra/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
