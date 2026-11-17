# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM node:22.23.5-trixie-slim@sha256:68c76cfad89921b927eae28ba21407475e29d0ce450afcdbe70c1532db042b64 AS frontend
WORKDIR /web
COPY src/apps/web/package.json src/apps/web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY src/apps/web/ ./
COPY src/packages/templates/reader-v18.js /packages/templates/reader-v18.js
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS dependencies
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM postgres:15.20-trixie@sha256:2663a9f0fde52de94f5dad3603a1942359f49472f1017c1a6d64f66bfedacb40 AS postgres_client
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS runtime
ARG SOURCE_COMMIT=uncommitted
LABEL org.opencontainers.image.title="Bilingual personal PDF library" org.opencontainers.image.revision=$SOURCE_COMMIT
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src HOME=/tmp
WORKDIR /app
# PostgreSQL 15 server and client share a major version. Exact dpkg versions are
# included in the built image inventory and release evidence.
RUN apt-get update --error-on=any && apt-get upgrade -y && apt-get install -y --no-install-recommends libpq5 liblz4-1 libzstd1 libreadline8t64 libgomp1 ca-certificates && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 library && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /tmp library \
    && mkdir -p /app/release && dpkg-query -W -f='${Package}\t${Version}\n' > /app/release/system-packages.tsv
COPY --from=dependencies /app/.venv /app/.venv
RUN /usr/local/bin/python -m pip uninstall --yes pip && /usr/local/bin/python -c "import shutil; shutil.rmtree('/usr/local/lib/python3.12/ensurepip')"
COPY --from=postgres_client /usr/lib/postgresql/15/bin/pg_dump /usr/local/bin/pg_dump
COPY --from=postgres_client /usr/lib/postgresql/15/bin/pg_restore /usr/local/bin/pg_restore
COPY --from=postgres_client /usr/lib/postgresql/15/bin/psql /usr/local/bin/psql
RUN pg_dump --version && pg_restore --version && psql --version
COPY src/apps/api/ /app/src/apps/api/
COPY src/packages/ /app/src/packages/
COPY src/workers/ /app/src/workers/
COPY res/schemas/ /app/res/schemas/
COPY deployment/parser-vlm-models.lock.json /app/deployment/parser-vlm-models.lock.json
COPY res/reference/ /app/res/reference/
COPY res/vendor/ /app/res/vendor/
COPY pyproject.toml uv.lock /app/
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
COPY --from=frontend /web/dist/ /app/src/apps/web/dist/
RUN python -c "from importlib.metadata import distributions; import json; from pathlib import Path; Path('/app/release/python-packages.json').write_text(json.dumps(sorted([{'name': d.metadata['Name'], 'version': d.version, 'license': d.metadata.get('License-Expression') or d.metadata.get('License', 'UNKNOWN')} for d in distributions()], key=lambda x:x['name']), indent=2))"
RUN python -c "from packages.parsers.models import parser_version; print(parser_version())"
ARG SOURCE_TREE_SHA256=unrecorded
LABEL dev.bilingual-library.source-tree-sha256=$SOURCE_TREE_SHA256
USER 10001:10001
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
