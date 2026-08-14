FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CODEX_HOME=/home/app/.codex

ARG TARGETARCH=amd64
ARG CODEX_CLI_VERSION=0.146.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gzip tar \
    && case "$TARGETARCH" in \
        amd64) CODEX_ARCH="x86_64"; CODEX_SHA256="5ba3b9405543953081f661d0854d266f76e2abbe51d41349355a36de7673776a" ;; \
        arm64) CODEX_ARCH="aarch64"; CODEX_SHA256="975bac91562abeedeb8f79636d51a86649b31f34a9de6a3bcb059565b6cf1f87" ;; \
        *) echo "Unsupported Docker architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --retry 3 --retry-delay 2 \
        "https://github.com/openai/codex/releases/download/rust-v${CODEX_CLI_VERSION}/codex-${CODEX_ARCH}-unknown-linux-musl.tar.gz" \
        --output /tmp/codex.tar.gz \
    && printf '%s  %s\n' "$CODEX_SHA256" /tmp/codex.tar.gz | sha256sum -c - \
    && mkdir -p /tmp/codex \
    && tar -xzf /tmp/codex.tar.gz -C /tmp/codex \
    && install -m 0755 "/tmp/codex/codex-${CODEX_ARCH}-unknown-linux-musl" /usr/local/bin/codex \
    && rm -rf /tmp/codex /tmp/codex.tar.gz /var/lib/apt/lists/*

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY app ./app
RUN mkdir -p /home/app/.codex && chown -R app:app /home/app/.codex

USER app
EXPOSE 8010

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=3).read()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010", "--proxy-headers", "--forwarded-allow-ips", "*"]
