# Development tests and repository checks; no parser models or provider credentials.
FROM node:22.23.5-trixie-slim@sha256:68c76cfad89921b927eae28ba21407475e29d0ce450afcdbe70c1532db042b64 AS frontend
WORKDIR /web
COPY src/apps/web/package.json src/apps/web/package-lock.json ./
RUN npm ci --ignore-scripts
COPY src/apps/web/ ./
COPY src/packages/templates/reader-v18.js /packages/templates/reader-v18.js
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85 AS uv
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src PATH=/app/.venv/bin:$PATH
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY . /app
COPY --from=frontend /web/dist/ /app/src/apps/web/dist/
RUN mkdir -p /app/.agent/tmp /app/.agent/harness && chown -R 10001:10001 /app/.agent
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-rs"]
