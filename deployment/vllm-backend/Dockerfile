FROM docker/model-runner:v1.2.9-cuda@sha256:ee3789655a824d9974510e491250c08a1fbf59e3b90c268c0d3db6ee55a5eed5 AS dmr
FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv

# Do not inherit DMR's reserved com.docker.desktop.service image label: Docker
# Desktop hides containers carrying that key from Compose's container discovery.
FROM nvidia/cuda:13.0.3-devel-ubuntu24.04@sha256:b7ae301dea2c162444795462ce17a05f6a516e5a75944b57af5b88540a1a2266 AS base
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
       python3.12 python3.12-venv python3.12-dev build-essential \
       curl ca-certificates libnuma1 libglib2.0-0t64 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 995 modelrunner \
    && useradd --system --uid 995 --gid modelrunner --groups video \
       --create-home --home-dir /home/modelrunner modelrunner \
    && mkdir -p /var/run/model-runner /models /app \
    && chown modelrunner:modelrunner /var/run/model-runner /models /app

FROM base AS environment-builder
COPY --from=uv /uv /usr/local/bin/uv
RUN mkdir /opt/vllm-env /opt/oxr-env && chown modelrunner:modelrunner /opt/vllm-env /opt/oxr-env
USER modelrunner
ENV UV_PYTHON_DOWNLOADS=never UV_CONCURRENT_DOWNLOADS=3 UV_CONCURRENT_INSTALLS=2

FROM environment-builder AS environment
COPY --chown=modelrunner:modelrunner requirements.lock /tmp/requirements.lock
RUN --mount=type=cache,target=/home/modelrunner/.cache/uv,mode=0777 uv venv --python /usr/bin/python3.12 /opt/vllm-env \
    && uv pip sync --python /opt/vllm-env/bin/python --require-hashes --only-binary :all: --torch-backend cu130 /tmp/requirements.lock \
    && uv pip check --python /opt/vllm-env/bin/python
RUN /opt/vllm-env/bin/python -c "import torch, vllm; assert torch.version.cuda == '13.0'; assert vllm.__version__ == '0.34.0'; print(vllm.__version__)" > /opt/vllm-env/version

FROM base AS standard
COPY --from=environment /opt/vllm-env /opt/vllm-env
COPY --from=dmr --chown=modelrunner:modelrunner /app /app
COPY --chown=modelrunner:modelrunner startup.py /app/vllm-cuda-startup.py
COPY --chown=modelrunner:modelrunner start.sh /app/vllm-cuda-start.sh
COPY --chown=modelrunner:modelrunner resources.py patch_cache.py /app/
RUN /opt/vllm-env/bin/python /app/patch_cache.py
# PyTorch wheels carry a consistent CUDA library set. Prepending the system
# toolkit here mixes its nvJitLink with wheel cuBLAS and breaks BF16/FP16 GEMM.
ENV MODEL_RUNNER_SOCK=/var/run/model-runner/model-runner.sock \
    MODEL_RUNNER_PORT=12434 \
    LLAMA_SERVER_PATH=/app \
    LLAMA_ARG_HOST=0.0.0.0 \
    LD_LIBRARY_PATH=/app:/usr/local/nvidia/lib:/usr/local/nvidia/lib64 \
    HOME=/home/modelrunner \
    MODELS_PATH=/models
WORKDIR /app
USER modelrunner
EXPOSE 12434 12435
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS "http://localhost:${MODEL_RUNNER_PORT}/engines/status" || exit 1
ENTRYPOINT ["/bin/sh", "/app/vllm-cuda-start.sh"]
LABEL io.paper-translation.backend="vllm-cuda" io.paper-translation.vllm-version="0.34.0"

FROM environment-builder AS oxr-environment
COPY --chown=modelrunner:modelrunner oxr-requirements.lock /tmp/oxr-requirements.lock
RUN --mount=type=cache,target=/home/modelrunner/.cache/uv,mode=0777 uv venv --python /usr/bin/python3.12 /opt/oxr-env \
    && uv pip sync \
       --python /opt/oxr-env/bin/python --require-hashes --only-binary :all: --torch-backend cu130 /tmp/oxr-requirements.lock
COPY --chown=modelrunner:modelrunner build_oxr_plugin.py oxr_launch.py /tmp/
RUN /opt/oxr-env/bin/python /tmp/build_oxr_plugin.py fetch /tmp/oxr-plugin \
    && uv pip install --python /opt/oxr-env/bin/python --no-deps --no-build-isolation /tmp/oxr-plugin \
    && uv pip check --python /opt/oxr-env/bin/python \
    && VLLM_PLUGINS=oxr /opt/oxr-env/bin/python /tmp/build_oxr_plugin.py verify /opt/oxr-env/capabilities.json

FROM standard AS oxr
COPY --from=oxr-environment /opt/oxr-env /opt/oxr-env
COPY --from=oxr-environment /tmp/oxr-plugin/LICENSE /app/licenses/oxr/LICENSE
COPY --chmod=0755 oxr_launch.py /app/vllm-oxr-launch
ENV VLLM_SERVER_PATH=/app/vllm-oxr-launch
LABEL io.paper-translation.oxr-vllm-version="0.25.1"

FROM standard AS default
