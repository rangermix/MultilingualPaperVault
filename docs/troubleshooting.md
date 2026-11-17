# Troubleshooting

Start with the document or task's visible status and recorded error code. A model
download, a queue waiting for resources, an execution failure, and an unknown
request outcome need different recovery steps.

Run deployment commands from the repository root using the same project name,
environment file, profiles, and overrides as the installed instance. Preserve
`compose.yaml` and named volumes while investigating.

## The application does not start or open

Check service status and recent output:

```bash
docker compose ps
docker compose logs --tail 100 app worker parser parser-models db migrate
```

- Confirm you copied the template for a new instance and built `app`, `parser`,
  and `db`. Source installs need those images; `up` alone is not a model setup.
- Open the published address and port, normally
  [http://127.0.0.1:8080](http://127.0.0.1:8080). Resolve a port conflict with `PORT`
  while retaining matching browser origins.
- `/health/live` means HTTP is responding. `/health/ready` checks bounded startup
  dependencies and fresh worker/parser heartbeats; it does not run model inference
  or hash the entire library. Explicit maintenance verification checks stored data.
- For host/origin rejection after changing the address, check `BIND_ADDRESS`,
  `ALLOWED_HOSTS`, and `APP_ORIGINS` together. Keep local access unless you have
  deliberately arranged trusted remote access; there is no application login.
- If the library appears empty after a move or update, compare the Compose project
  and volume names with the original deployment before creating more data.

An old local configuration may refer to a removed parser image recipe or omit new
networks/services. Follow the existing-instance notes in
[Compose deployment](deployment/README.md); do not recreate retired native parsers
or replace the local configuration blindly.

## Parsing fails or a model remains unavailable

- Verify the selected executable parser and the configured DMR backend/URL. The
  parser requires Docker-managed full-page image inference. A running app or
  prepared weight cache does not prove backend support for the model.
- `PARSER_DMR_BACKEND_UNAVAILABLE` means the selected engine is unavailable.
  `PARSER_DMR_MODEL_MISMATCH` means the exact expected artifact identity was not
  returned. Check the engine/configuration rather than selecting a substitute
  silently.
- `PARSER_DMR_CONFIGURATION_FAILED` reports a rejected backend configuration.
  Inspect the backend's logs and compatibility. Already verified downloaded files
  can be reused on the next explicit preparation.
- `PARSER_MODEL_ACCESS_REQUIRED` reports that ProKope model access is needed.
  For `PARSER_MODEL_PLUGIN_REQUIRED`, check the [OXR CUDA Runner setup](deployment/extraction-acceleration.md#oxr-on-the-managed-cuda-runner).
- Retired Docling/Granite/Paddle/Xiaomi/TeleOCR or native-device snapshots do not
  switch automatically. Existing saved source can still be read, translated, and
  exported without reparsing.
- For interrupted or corrupt downloads, check free disk space, connectivity, and
  the reported hash/path error. Preserve verified cache files; use explicit model
  preparation again after fixing the cause.

Follow [Parser setup](deployment/extraction-acceleration.md) for backend contracts,
storage, telemetry, and Metal-specific limits. Do not install inference libraries
inside running application containers.

## Work stays queued or waits for resources

Inspect **Settings → Resources and concurrency** and the task's waiting reason.
The shared RAM/VRAM policy admits model loads and work using current telemetry and
estimated model allocations. A waiting task need not be stuck or have failed.

- Check available memory, other resident models, and active work. Parser work is
  serial even when the main-operation ceiling is higher.
- Missing GPU telemetry holds local CUDA work. Configure the required private
  telemetry endpoint for an external Docker-managed runner.
- Lowering a limit does not interrupt a request already running. Wait for it to
  finish before expecting memory or concurrency capacity to be released.
- A model's download size and parameter count do not establish its peak memory.
  Do not bypass admission just to make a queued task start.

## Translation does not start or uses older settings

- Save a complete service configuration with the exact URL, protocol,
  authentication, and model ID. Saving does not test the service.
- Check whether model requests were paused by maintenance or recovery. The
  Settings notice has the separate recovery action; reopening ordinary writes
  does not automatically enable dispatch.
- If cost controls are enabled, provide the required pricing and positive job
  budget. Disabled cost controls do not remove provider charges.
- Source-only uploads do not authorize translation. Start translation explicitly
  and check the displayed destination and target language.
- Existing jobs retain their frozen service and credential revision. Changing
  Settings applies to new tasks; it does not retarget old requests.
- A stopped optional local sidecar, unsupported backend, or insufficient memory
  can leave a local model selectable but unavailable. Follow
  [Local translation and analysis](deployment/local-translation.md).

## A request has an unknown outcome

A timeout or lost connection after dispatch can leave the result and charge
unknown. The application does not automatically resend such a request. Inspect
the attempt, the service's own records when available, and the task's explicit
resolution/risk action before retrying. Restarting containers does not settle an
unknown request, and acknowledging risk does not prove that it was free.

## A passage, table, formula, or translation is wrong

Open the original PDF/page comparison and inspect extraction evidence before
changing text. Use a PDF-backed source correction for an extraction error, or edit
the translation/request a candidate for a translation error. Human review remains
optional. Model quality findings are nonblocking, so a published result still
needs checking where accuracy matters.

Unsupported or damaged content can appear as original text or imagery with a
finding. Missing fine coordinates are not precise cell/glyph locations. Changing
the reader template cannot repair OCR or retranslate a passage; it renders the
saved revisions.

If an export uses an earlier version, check which publication you selected.
Explicit draft exports keep missing translations as original content. Offline
exports omit links back to the running instance by design.

## A save conflicts or data verification fails

For a stale-version conflict, refresh the latest document/settings and compare
before saving. Another tab or worker may have changed the object. Repeatedly
sending the same stale save will not resolve it.

For corrupt-resource, manifest, migration-checksum, or database errors, retain
the evidence and your verified backup. Do not edit installed migrations or sealed
files in place. Follow [Backup and restore](ops/restore.md) for explicit integrity
verification and recovery. Do not remove volumes as a troubleshooting shortcut.

## Reporting a problem

Read [Contributing](../CONTRIBUTING.md) before opening an issue. Include the source
commit, OS, Compose/backend versions, relevant image/model IDs, exact steps,
expected and actual behavior, and minimal redacted task/log evidence. Distinguish
an application display problem from the inference backend's actual result.

Do not upload your database, provider store, full backups, private PDFs, credentials,
or raw network captures. Logs and inference receipts can contain document text;
inspect them before sharing. Use a small redistributable or synthetic PDF when
possible. Report vulnerabilities through [Security](../SECURITY.md).
