# Paper Translation guides

Paper Translation is a personal PDF library for translation, bilingual reading,
editing, and offline export. Start with [Installation](installation.md), then
[Using the library](usage.md).

These guides describe the current source tree. Source capabilities, executed
tests, and the state of a running installation are separate evidence; an older
test report does not certify your deployment or selected model.

## User guides

| Guide | What you will find |
| --- | --- |
| [Installation](installation.md) | Compose setup, DMR prerequisites, persistent data, and upgrades |
| [Using the library](usage.md) | Settings, PDFs, translation, editing, reading, and exports |
| [Troubleshooting](troubleshooting.md) | Common failures, recovery actions, and useful diagnostic evidence |
| [Backup and restore](ops/restore.md) | Verified backups, maintenance mode, restore, and database upgrades |
| [Retention and cleanup](ops/retention.md) | Storage retention and bounded maintenance commands |

The application serves one library without accounts or access controls. Run it
on your own hardware, retain the default loopback binding unless you have arranged
trusted access, and keep its persistent volumes when updating. See
[Security](../SECURITY.md) for the deployment and reporting boundaries.

## Deployment references

| Guide | Contents |
| --- | --- |
| [Compose deployment](deployment/README.md) | Services, profiles, configuration, and existing-instance changes |
| [Parser setup](deployment/extraction-acceleration.md) | DMR full-page parsers, downloads, prerequisites, and memory estimates |
| [Local translation and analysis](deployment/local-translation.md) | GGUF/llama.cpp, Safetensors/vLLM, and Apple Silicon MLX choices |
| [MLX backend](deployment/mlx-backend.md) | Build, installation, verification, and rollback of the custom Metal payload |
| [Dependency evidence](ops/dependencies.md) | Locks, model caches, image inventories, and scan requirements |
| [Third-party notices](../THIRD_PARTY_NOTICES.md) | Bundled resources and optional model licensing boundaries |

## Development references

| Guide | Contents |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | Reports, development workflow, validation, and pull requests |
| [Product scope](product-baseline.md) | Implemented capabilities and boundaries |
| [Architecture](architecture.md) | Process boundaries, storage, revisions, and concurrency |
| [Workflows](workflows.md) | Processing, recovery, original-only content, and task history |
| [Task model](task-model.md) | User-facing operations, internal steps, and attempts |
| [API](api.md) | Route groups, schemas, concurrency, and request handling |
| [UI behavior](ui-ux.md) | Current interactions and their verification entry points |
| [UI specification](ui-ux-spec.md) | Detailed interaction requirements and the dated audit baseline |
| [Tests](../tests/README.md) | Isolated Linux/PostgreSQL checks and evidence limits |
| [Browser tests](../tests/browser/README.md) | Mocked UI checks and explicit disposable-instance acceptance |
| [Runtime resources](../res/README.md) | Schemas, frozen reader assets, and controlled seed provenance |

Python applications and domain code live in `src/`, runtime assets in `res/`,
test inputs in `tests/`, and image/backend inputs in `deployment/`.

Return to the [project overview](../README.md) for the quick start. See
[AGENTS.md](../AGENTS.md) for coding agent guidance.
