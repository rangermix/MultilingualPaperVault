# Contributing to Paper Translation

Contributions are welcome: bug reports, code, tests, documentation, and translations.
Read the [project overview](README.md), [user guides](docs/README.md), and
[product scope](docs/product-baseline.md) before proposing a change. Coding agents
must also follow [AGENTS.md](AGENTS.md).

## Scope and repository

Paper Translation is a single-instance personal PDF library, deployed through
Docker Compose on the user's own hardware. It includes FastAPI, a React management
UI, PostgreSQL, durable workers, an isolated parser, and Docker Model Runner
integration. Accounts, workspaces, roles, non-PDF import routes, and automatic
provider/model fallback are outside the current product scope.

| Location | Purpose |
| --- | --- |
| `src/apps/api/`, `src/apps/web/` | HTTP API and React UI |
| `src/packages/` | Domain logic, migrations, providers, publishing, and maintenance |
| `src/workers/` | Durable worker and isolated PDF parser |
| `res/` | Runtime schemas, frozen reader resources, and controlled seed materials |
| `tests/` | Regression tests, authored fixtures, browser checks, and test image |
| `deployment/` | Product image recipes, backend inputs, and model/dependency locks |
| `docs/` | User guides, operations, and technical references |
| `.agent/tmp/` | Ignored logs, screenshots, scratch scripts, and run evidence |
| `.agent/local-data/` | Ignored persistent private state and authorization records |

The default branch and PR target are `main`. Project-owned contributions use the
[GNU Affero General Public License, version 3 only](LICENSE) (`AGPL-3.0-only`).
Preserve third-party licenses and notices, and contribute only material you may
share under its applicable terms. Read [Third-party notices](THIRD_PARTY_NOTICES.md)
before adding dependencies, models, fonts, papers, or other redistributable assets.

## Reporting bugs and proposing changes

Search the repository's issues and pull requests, including closed reports.
Use one issue per problem and include:

- The source commit, OS, installation details, Docker/Compose version, and browser
  when relevant. Include exact image IDs and parser/model/backend identities for
  inference problems.
- Reproduction steps, expected behavior, actual behavior, frequency, and the last
  known working revision if this is a regression.
- Minimal redacted task errors/logs and troubleshooting results. Separate source
  capability, tests you actually ran, and observed runtime behavior.
- A small synthetic or redistributable PDF when needed. Explain which page or
  passage is wrong and whether the error is in extraction, translation, or display.

Never attach provider secrets, unredacted network captures, database dumps, full
backups, or private papers. Model receipts and logs may include paper text. A
support request does not authorize someone to read your real credentials. Use
[Security](SECURITY.md) for vulnerabilities and sensitive reports.

For a feature, describe the user problem, concrete use case, proposed behavior,
alternatives, and observable acceptance criteria. Discuss substantial architecture
or scope changes before implementing them. Small, focused fixes can go directly
to a PR.

## Development and validation

Run commands from the repository root. The reproducible Linux/PostgreSQL workflow
needs Docker and Compose and installs locked dependencies while building its test
image. It does not need real provider keys or downloaded model weights.

Use a distinct project and the tracked template for checks and tests:

```bash
docker compose -p paper-checks -f compose.example.yaml run --build --rm checks
docker compose -p paper-tests -f compose.example.yaml run --build --rm tests
docker compose -p paper-tests -f compose.example.yaml --profile tests down --volumes
```

The cleanup command is only for that disposable test project. Never substitute
the user's project or local `compose.yaml`. Do not use profile-wide `up` to run
tests; it also starts default product services. Pick a different `TEST_DB_PORT`
if the dedicated test port is in use and retain it for the whole test run.

For host development, Python requirements are declared in `pyproject.toml` and
locked in `uv.lock`; the packaged environment uses Python 3.12. The frontend and
test images use Node.js 22 with `src/apps/web/package-lock.json`. Follow
[Tests](tests/README.md) for supported host setup, focused checks, and frontend
unit/build commands, and [Browser tests](tests/browser/README.md) for UI changes.
Set `PYTHONPATH=src` for host Python module commands; pytest configures it already.

Test doubles establish application contracts, not real service compatibility,
model quality, or GPU/Metal behavior. Record skips and missing prerequisites.
Real inference needs explicit content/destination authorization and a budget when
applicable. Never use the installed library or real credentials as test fixtures.
CI configuration lives in [`.github/workflows/ci.yml`](.github/workflows/ci.yml);
local results do not prove that a remote workflow has passed.

## Implementation boundaries

- Preserve unrelated work, local Compose settings, project identity, and volumes.
  Runtime dependencies belong in image builds; weights download only on explicit
  preparation/use with pinned revisions, sizes, and hashes.
- Append database migrations. Do not alter installed migration bytes, sealed
  snapshots, published files, or existing reader identities in place.
- Retain CAS, generations, fencing, leases, idempotency, deletion guards, and
  maintenance locks. Single-instance use still includes concurrent tabs/workers.
- Keep parser inputs, model preparation, database access, and provider secrets
  separated. Provider keys stay in backend secret files and out of logs/exports.
- Keep content findings nonblocking and human review optional. Execution failures,
  authorization, uncertain outcomes, unsafe paths, and version conflicts retain
  their actual safeguards. Never automatically resend an uncertain paid request.
- Keep user instructions in the public guides, contributor workflow here, and
  architecture constraints in `AGENTS.md`. Put run-specific evidence under a unique
  `.agent/tmp/` directory; never clean `.agent/local-data/` as temporary output.

See [Architecture](docs/architecture.md) and [Workflows](docs/workflows.md) for the
complete behavior. Existing model, schema, and reader IDs are compatibility
identities, not project-release numbers.

## Pull requests

Use a focused branch and describe the problem and resulting behavior for someone
who has not seen the investigation. Include:

- The scope and linked issue, with screenshots for visible UI changes where useful.
- Actual validation commands/results, skipped checks, source/environment details,
  and remaining limitations.
- Relevant regression coverage and updated user/developer documentation.
- Any migration, deployment, compatibility, licensing, or data-preservation impact.

Keep secrets, private data, unrelated edits, and generated output out of the diff.
Do not claim real model calls, approval, CI success, or a completed deployment from
test doubles or static checks. Maintainers review and decide when to merge or
release. Follow the [installation update guide](docs/installation.md#updating-an-existing-instance)
when updating an existing installation.
