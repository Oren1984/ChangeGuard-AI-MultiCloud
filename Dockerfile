# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Trusts any extra CA certificates dropped in ./certs (e.g. a corporate TLS
# -inspection root) before installing dependencies. The directory is empty
# by default (kept via certs/.gitkeep; real certs are gitignored), so this
# is a no-op on a normal, unrestricted network.
COPY certs/ /usr/local/share/ca-certificates/extra/
RUN update-ca-certificates

COPY pyproject.toml ./
COPY src ./src

ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install .


FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system changeguard \
    && useradd --system --gid changeguard --home-dir /app --shell /usr/sbin/nologin changeguard

WORKDIR /app

COPY --from=builder /install /usr/local
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY templates ./templates
COPY static ./static
COPY demo ./demo

RUN chown -R changeguard:changeguard /app

USER changeguard

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
