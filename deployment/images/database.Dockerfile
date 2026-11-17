# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM postgres:15.20-trixie@sha256:2663a9f0fde52de94f5dad3603a1942359f49472f1017c1a6d64f66bfedacb40
ARG SOURCE_COMMIT=uncommitted
LABEL org.opencontainers.image.title="Personal library PostgreSQL 15" org.opencontainers.image.revision=$SOURCE_COMMIT
# Build-time security updates are recorded in the resulting immutable image.
# Runtime is always uid999; the root-only gosu privilege-switch branch is unused.
RUN apt-get update --error-on=any && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && rm /usr/local/bin/gosu \
    && mkdir -p /usr/local/share/library-release \
    && dpkg-query -W -f='${Package}\t${Version}\n' > /usr/local/share/library-release/system-packages.tsv
COPY LICENSE /usr/local/share/library-release/PROJECT-LICENSE
ARG SOURCE_TREE_SHA256=unrecorded
LABEL dev.bilingual-library.source-tree-sha256=$SOURCE_TREE_SHA256
USER 999:999
