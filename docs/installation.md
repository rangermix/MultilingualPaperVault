# Installation

Run Paper Translation as one Docker Compose instance on your own computer or
home server. The application has no accounts or access controls and binds to
`127.0.0.1:8080` by default. Keep that binding for access from the host.

## Requirements

- Git and Docker with the `docker compose` command. Use Docker Engine 28.0
  or later, including the engine bundled with Docker Desktop. The parser bridge
  uses the [isolated gateway mode](https://docs.docker.com/engine/release-notes/28/#port-publishing-in-bridge-networks).
- A Docker-managed inference backend compatible with the selected parser and its
  image-input contract. All executable parsers require Docker Model Runner (DMR).
- Enough disk space for images, PDFs, generated pages, backups, and the selected
  model cache. DMR also retains an imported copy of model weights; budget roughly
  twice their download size before runtime working space.
- Sufficient RAM/VRAM for the model and inference backend. Download size is not a
  memory requirement or a speed/quality measurement.

The API, worker, parser, model preparation, and parser relay share the
application image. Its build inputs support amd64 and arm64. This does not certify every model or backend on both
architectures. Configure a supported CUDA/vLLM backend or Apple Silicon Metal/MLX
backend using [Parser setup](deployment/extraction-acceleration.md). There is no
standalone native or CPU-parser fallback. Apple Silicon's custom payload needs
the additional [MLX backend procedure](deployment/mlx-backend.md).

Optional local translation has its own engine/model compatibility requirements;
see [Local translation and analysis](deployment/local-translation.md). An external
translation API does not remove the parser's DMR requirement.

## Create a source installation

These commands build the checked-out source; they do not select a published
application image. Replace `REPOSITORY_URL` with the clone URL for this source,
or open the extracted directory if you downloaded a source archive. Run shell
commands from the repository root.

```bash
git clone -c core.autocrlf=false REPOSITORY_URL Paper-Translation
cd Paper-Translation
```

Keep `core.autocrlf=false` for this checkout. The repository enforces LF for
normal text and preserves the registered bytes of frozen resources on every
platform. If an older Windows checkout reports a migration or template hash
mismatch, build from a fresh clone and keep your existing Compose configuration
and named volumes.

Copy the template **only for a new installation**. In Bash (Linux, macOS, or WSL):

```bash
cp compose.example.yaml compose.yaml
```

In Windows PowerShell:

```powershell
Copy-Item compose.example.yaml compose.yaml
```

Edit the ignored local `compose.yaml` and, where needed, its environment file:

- Set `PARSER_DMR_BACKEND` to the provisioned `vllm` or `mlx` backend and confirm
  `PARSER_DMR_URL` reaches that Docker-managed runner from the containers.
- Apply the backend, network, and telemetry requirements in
  [Parser setup](deployment/extraction-acceleration.md). Installing Docker alone
  does not establish a working image-inference backend.
- Keep the loopback bind unless you deliberately arrange trusted access. Changing
  the address also requires matching allowed hosts and browser origins; the app
  does not add a login page or a reverse proxy.
- Enable optional local translation only after following its deployment guide.
  Keep provider endpoints and API keys in application Settings, not Compose files.

CUDA admission also needs RAM/VRAM telemetry. For an external runner, set
`RESOURCE_MONITOR_URL` in the Compose environment to a compatible monitor.
The template passes that address to `parser-dmr` and `parser-models`.
Set the same address explicitly on `local-translator` if it uses that monitor.
The default monitor uses the optional bundled `vllm-runner`. If you choose
that runner, follow its [CUDA setup](deployment/local-translation.md#cuda-vllm-through-compose-on-windowswsl2)
and set `PARSER_DMR_URL=http://vllm-runner:12434` in the Compose environment.
Keep the parser's internal relay URLs from the template. Check Settings
resource status before processing.

Validate, build, and start:

```bash
docker compose config --quiet
docker compose build app parser db
docker compose up -d --wait
docker compose ps
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). Set a different `PORT` in the
Compose environment if that port is already used. Use the same environment file,
profiles, project name, and override files for subsequent commands.

The default application stack can start without translation credentials or
downloaded model weights. That readiness does not prove inference is available.
In **Settings → PDF parsing**, choose an executable parser and explicitly prepare
it, then process a PDF you are allowed to use. Check the resulting task and compare
its reading output with the original. Surya OCR 2 is the default for new settings;
OXR requires the [managed CUDA Runner with its plugin enabled](deployment/extraction-acceleration.md#oxr-on-the-managed-cuda-runner).
ProKope is still gated on model access. A real PDF task exercises the prepared
model and its output decoder.

Builds install locked dependencies. Startup and saving settings do not download
models; explicit preparation or first processing use does. Model download and
inference can take substantially longer than application startup.

Follow [Using the library](usage.md) to configure translation and process papers.

## Persistent data and normal shutdown

Compose named volumes retain the database, original PDFs, source and translation
history, publications, settings, model caches, and backups. Their identities depend
on the configured project and volume names. Starting the same source under a
different project name can produce an empty library using new volumes.

The `provider_config` volume contains saved translation settings and credential
revisions used by existing tasks. Preserve it during ordinary updates. Standard
library backups exclude those settings and secrets; configure the provider again
when restoring onto a new host. Backups also exclude re-downloadable model caches.

To stop the installed instance, use its original Compose options:

```bash
docker compose down
```

This preserves named volumes. Do not add `--volumes`; it removes persistent data.
Use [Backup and restore](ops/restore.md) to move or restore an instance rather
than copying live database files.

## Updating an existing instance

1. Record the current source commit, image IDs, Compose project, configuration
   files, enabled profiles, and volume names. Retain the old images for rollback.
2. Create and verify a backup using [Backup and restore](ops/restore.md). That
   procedure leaves maintenance enabled and model dispatch paused until you
   explicitly reopen them.
3. Update your source checkout without discarding local work. For a clean checkout
   following its configured branch, `git pull --ff-only` refuses a divergent merge.
4. Compare `compose.example.yaml` with your local configuration. Merge required
   service/network changes while preserving project identity, volume names, image
   bindings, backend settings, and local overrides. Do not overwrite `compose.yaml`.
   Follow [parser isolation setup](deployment/extraction-acceleration.md#on-demand-preparation-and-isolated-execution)
   to migrate any direct parser backend overrides into the relay.
5. With the instance's original Compose options, validate and rebuild using
   `docker compose config --quiet`, `docker compose build app parser db`, then
   `docker compose up -d --wait`.
6. Check service status, existing documents, and the changed feature. Reopen
   ordinary writes and model dispatch through the maintenance/recovery steps in
   the backup guide when appropriate. A ready application does not establish that
   a particular model, publication, or restore has been verified.

Database major-version or base-distribution changes need the separate migration
procedure in [Backup and restore](ops/restore.md). Do not attach an older database
volume to a changed base or attempt rollback by changing only the application
image. Existing queued jobs keep their original model/profile snapshots; retired
parser choices require an explicit replacement for new work.
