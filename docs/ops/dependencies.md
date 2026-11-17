# Dependency evidence

API, worker, parser and preparation share one image. Base images are pinned by
registry digest. `uv.lock` pins the Python dependency closure and hashes; the
frontend uses `src/apps/web/package-lock.json`. Runtime images include the built web
bundle, native libraries and per-image Python/system package inventories under
`/app/release/`. A runtime manifest records installed system-package versions;
the final image digest identifies their exact bytes.

`deployment/parser-vlm-models.lock.json` is the active parser model allowlist.
Models are absent from image layers. The separate `parser-models` service downloads
only the selected profile's pinned files on explicit preparation or first use.
Downloads are bounded by byte count, hash checked, written atomically and reused
after restart. Completed verified files survive an interrupted download. The
application image includes no Torch, Transformers, Paddle, Docling or ONNX runtime;
Docker Model Runner supplies inference for the full-page parsers. The parser
mounts its cache read-only and has no database or translation credentials.
Archived parsers/dependency locks are excluded from image inputs.
Optional translation weights have their own `src/packages/local_models/models.lock.json`
and are downloaded only on explicit use; settings reads and startup do not prepare
them. See [local translation](../deployment/local-translation.md).

`deployment/images/database.Dockerfile` derives the nonroot PostgreSQL 15 runtime
from its fixed Trixie base, applies OS updates during build and removes the
root-only privilege-switch helper. For release validation, use
`docker compose build --pull --no-cache app parser db` so the apt update and
upgrade steps fetch current Trixie security packages. Scan those exact images
and record any native linkage limits.

The PostgreSQL server and the app's `pg_dump` and `pg_restore` tools use PostgreSQL
15. The tools link to Debian's system `libpq5`. The psycopg binary wheel carries
its own libpq, reported by `psycopg.pq.version()`. Check the installed versions
when reviewing PostgreSQL advisories and running backup/restore tests. Release
records must include the actual app/parser/db image IDs and digest,
source commit plus source-tree hash, architecture, all dependency locks, model
manifest, license notices and vulnerability scan results. Unknown or missing
license fields require review; generating an inventory is not legal clearance.

## Unfixed OS advisories

Retain findings against the exact scanned image and recheck their distribution
status when preparing updates. A missing fixed version does not make a finding
harmless. Available stable updates should still be installed by the
existing build-time package update/upgrade steps, followed by a fresh image scan.

A review on 4 November 2026 found CVE-2026-6653 in the database image's linked
libxml2 package, `2.12.7+dfsg+really2.9.14-2.1+deb13u3`. Its version represents a
Debian 2.9.14-based implementation despite the leading 2.12.7. The
[Debian tracker](https://security-tracker.debian.org/tracker/CVE-2026-6653)
marks this Trixie package vulnerable with no fixed Trixie version and a
`no-dsa`/minor-issue classification. The image scanner's critical rating is a
different assessment. Static application review identified no ordinary SQL/XML
entry path, but that does not prove the linked component unexploitable.

Keep the database private and retain its nonroot, read-only, capability-dropping
container controls. Recheck Debian's stable status and rebuild/rescan the exact
images when a compatible fix is available; verify backups, startup and application
behavior before redeployment, preserving the PostgreSQL major version, settings
and volumes. Do not remove libxml2 from the current image: PostgreSQL links it and
needs it at load time. A build without XML support would need separate dependency,
extension, compatibility and restore validation. Do not mix unstable libraries
into Trixie or force a distribution/database migration to clear scanner counts.
