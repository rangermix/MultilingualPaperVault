FROM --platform=$BUILDPLATFORM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv
FROM --platform=$BUILDPLATFORM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_NO_CONFIG=1 MACOSX_DEPLOYMENT_TARGET=15.0
COPY build-requirements.lock requirements.lock /build/
RUN uv venv --python 3.12 /build/venv \
    && uv pip sync --python /build/venv/bin/python --require-hashes /build/build-requirements.lock
COPY runtime /vllm-metal
# GitHub source archives omit the Git metadata needed by mlx-lm's setuptools-scm.
RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_MLX_LM=0.32.3.dev12+g4cfc64784 \
    uv pip sync --python /build/venv/bin/python --python-platform aarch64-apple-darwin \
      --target /vllm-metal/lib/python3.12/site-packages --require-hashes --no-build-isolation /build/requirements.lock
RUN chmod 755 /vllm-metal/bin/python3 && printf dev > /vllm-metal/.vllm-metal-version
COPY sitecustomize.py /vllm-metal/lib/python3.12/site-packages/sitecustomize.py
FROM scratch
LABEL org.opencontainers.image.title="Paper Translation Docker-managed vLLM Metal backend" org.opencontainers.image.version="0.33.0" io.paper-translation.runtime-platform="darwin/arm64"
COPY --from=build /vllm-metal /vllm-metal
