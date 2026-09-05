FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim

LABEL org.opencontainers.image.source=https://github.com/facebookresearch/gcm

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

RUN gcm-sentinel --help

ENTRYPOINT ["gcm-sentinel"]
CMD ["serve"]
