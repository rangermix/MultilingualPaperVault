# Paper Translation · 对照文库

A personal PDF library for translation, bilingual reading, editing, and offline export.

Upload a paper, extract its content with a local Docker Model Runner backend, and
translate through your chosen API service or optional local model. Compare the
result with the original PDF, edit passages, and keep earlier reading versions.

- Organize PDFs with search, tags, stars, and an archive.
- Parse complete pages, including tables, equations, code, and nested content.
- Translate into your chosen language, with optional paper context and terminology.
- Edit translations and extraction corrections without replacing sealed history.
- Read bilingual pages and export self-contained HTML or a resource bundle.
- Keep source PDFs, settings, and publications in persistent Docker volumes.

This is a single-instance application for personal use on your own hardware.
It has no accounts or access controls. The default address is local to the host;
every client that can reach the service can operate the library.

## Quick start

Install Git, Docker with Compose, and a compatible **Docker Model Runner (DMR)
inference backend**. Parsing requires DMR; starting the application containers does
not install an inference engine. Choose and configure the backend using the
[installation guide](docs/installation.md) and [parser setup](docs/deployment/extraction-acceleration.md)
before processing a PDF.

For a new installation, replace `REPOSITORY_URL` with the clone URL for this
source and run the commands from Bash (Linux, macOS, or WSL).

```bash
git clone -c core.autocrlf=false REPOSITORY_URL Paper-Translation
cd Paper-Translation
cp compose.example.yaml compose.yaml
```

Set the backend and hardware options in your local `compose.yaml` or its Compose
environment, then build and start:

```bash
docker compose config --quiet
docker compose build app parser db
docker compose up -d --wait
docker compose ps
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). In Settings, select and prepare
the parser. Save a translation service if you want translated reading versions,
then upload a PDF. Saving settings does not download models or send a test request.
Explicit preparation or first use downloads the selected pinned weights.

These instructions build the current source. Windows PowerShell commands,
backend prerequisites, storage requirements, and update steps are in
[Installation](docs/installation.md).

## Using the library

Choose source-only processing to generate a reading version without translation,
or choose parsing and translation and check the displayed service and language
before submitting. Translation services may charge even when cost controls are off.
API keys are saved in backend files; they are not returned to the browser.

Quality findings remain visible alongside original content and do not require
human review to publish or export. OCR and translation can still omit or change
content; compare important passages, numbers, tables, and equations with the PDF.
See [Using the library](docs/usage.md) for the complete workflow.

## Updating

Keep your existing `compose.yaml`, Compose project name, environment files, image
bindings, and named volumes. Back up and verify the instance before upgrading.
Merge required template changes into the local configuration; copying the template
over an existing file can lose your settings or select different storage.
Follow [Updating an existing instance](docs/installation.md#updating-an-existing-instance)
and [Backup and restore](docs/ops/restore.md). Never use `down --volumes` to update
your library.

## Guides and help

| Guide | What you will find |
| --- | --- |
| [Installation](docs/installation.md) | Source setup, DMR prerequisites, persistent data, and updates |
| [Using the library](docs/usage.md) | Settings, uploads, translation, editing, reading, and export |
| [Troubleshooting](docs/troubleshooting.md) | Startup, parser, translation, resource, and recovery problems |
| [Documentation index](docs/README.md) | User guides, operations, and technical references |
| [Contributing](CONTRIBUTING.md) | Bug reports, development, validation, and pull requests |
| [Security](SECURITY.md) | Deployment boundaries, private reporting, and sensitive data |

The four executable parsers are Surya OCR 2, Chandra OCR 2, and Infinity-Parser2
Pro/Flash. ProKope and OXR are listed as unavailable until their runtime and output
prerequisites are met. A portable client build, prepared model, or passing fixture
test does not establish inference quality or hardware compatibility. See
[Product scope](docs/product-baseline.md) for the supported behavior and limits.

Use the repository's issue tracker for reproducible problems. Follow the evidence
and privacy guidance in [Contributing](CONTRIBUTING.md).
Use the private reporting process in [Security](SECURITY.md) for vulnerabilities.

## License

Copyright (c) 2026 Fengqing Liu.

Except for third-party material, Paper Translation is licensed under the
[GNU Affero General Public License, version 3 only](LICENSE)
(`AGPL-3.0-only`). It is distributed without any warranty; see the license for
the full terms. Bundled resources, dependencies, and optional model weights
retain their original licenses, copyright notices, and attribution requirements;
see [Third-party notices](THIRD_PARTY_NOTICES.md) before redistribution.
