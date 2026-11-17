# Extend the Docker-managed Metal payload with translation settings.
ARG BASE_BACKEND=local/paper-translation-vllm-metal:0.33.0
FROM ${BASE_BACKEND} AS existing
FROM --platform=$BUILDPLATFORM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS patch
COPY --from=existing /vllm-metal /vllm-metal
COPY deployment/local-translation-backend/patch.py /patch.py
COPY deployment/local-translation-backend/translation_startup.py /vllm-metal/lib/python3.12/site-packages/translation_startup.py
COPY src/packages/local_models/ /catalog/
RUN python /patch.py
FROM scratch
LABEL org.opencontainers.image.title="Paper Translation Docker-managed MLX translation backend" io.paper-translation.runtime-platform="darwin/arm64"
COPY --from=patch /vllm-metal /vllm-metal
