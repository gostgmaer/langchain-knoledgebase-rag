# syntax=docker/dockerfile:1.7
# Base image is overridable so a build can reuse the copy already in the local
# image store when Docker Hub's layer CDN is unreachable (this machine's
# recurring `tls: bad record MAC`): pin it to the local digest, e.g.
#   docker compose build --build-arg PYTHON_BASE=python:3.14-slim@sha256:<digest>
# (`docker image inspect python:3.14-slim --format '{{json .RepoDigests}}'`).
ARG PYTHON_BASE=python:3.14-slim
# ============================================================
# Stage 1 - Builder
# ============================================================
FROM ${PYTHON_BASE} AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
# Venv lives OUTSIDE /app on purpose: docker-compose.yml bind-mounts the
# source tree over /app for live code, which would hide an /app/.venv. The
# old workaround (an anonymous `/app/.venv` volume) silently kept serving
# the FIRST build's packages forever — Compose preserves anonymous volumes
# across container recreation, so a rebuild after a uv.lock bump never
# reached the running container (confirmed live: cryptography/pyjwt/
# oauthlib/pypdf were all behind uv.lock). /opt/venv can't be shadowed.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
# This network intermittently corrupts downloads in transit (apt reports
# `Hash Sum mismatch`, registries `tls: bad record MAC`) — confirmed live on
# the host too, not just inside Docker. Without retries, one bad file out of
# a whole fetch failed the entire build. uv's own default is 3.
ENV UV_HTTP_RETRIES=8

WORKDIR /app

RUN apt-get -o Acquire::Retries=8 update && apt-get -o Acquire::Retries=8 install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installed from PyPI, not `COPY --from=ghcr.io/astral-sh/uv:latest` —
# this environment's network reliably reaches Docker Hub and PyPI but
# not ghcr.io (confirmed live: a plain `docker pull ghcr.io/...` fails
# identically with `tls: bad record MAC`, while docker.io/pypi.org
# pulls succeed), so routing uv's own install through ghcr.io was the
# actual build blocker, not anything about this image.
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

# Cache mount persists uv's download/wheel cache across separate
# `docker build` invocations (BuildKit keeps it on the host, outside
# any image layer) — without it, every single build re-downloaded
# every package (~200, including a 187MB torch) from scratch, which
# confirmed live is what turned this environment's ordinary transient
# network blips into repeated full-build failures. UV_LINK_MODE=copy
# (above) is required alongside this: uv's default hardlink-from-cache
# mode would leave dangling links once the ephemeral cache mount is
# gone, since only COPY/RUN-written files actually land in the image.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
    --locked \
    --no-dev

# ============================================================
# Stage 2 - Runtime
# ============================================================
FROM ${PYTHON_BASE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# -m creates a real, owned /home/app — confirmed live this was missing:
# a plain `useradd -r` system account gets no home directory on disk,
# so the cross-encoder reranker's lazy model download (sentence-
# transformers, first real use only — see packages/knowledge/reranking/
# cross_encoder.py) crashed with PermissionError trying to create
# ~/.cache/huggingface the first time an actual RAG query needed
# reranking, since nothing had ever exercised this path in a fresh
# container before.
RUN groupadd -r app && useradd -r -m -g app app \
 && install -d -o app -g app /home/app/.cache/huggingface

# --chown at COPY time, not a separate `RUN chown -R` afterwards: a
# metadata-only chown on files already materialized by an earlier COPY
# layer forces Docker to re-copy their full content into the new layer
# (its layer model has no concept of "metadata changed, content
# didn't") — confirmed live, that one RUN chown -R line was doubling
# this image's real size (~2.2GB re-copied for nothing).
COPY --chown=app:app --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

COPY --chown=app:app . .

USER app

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=20s \
    --retries=3 \
CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "packages.api.app:app", "--host", "0.0.0.0", "--port", "8000"]