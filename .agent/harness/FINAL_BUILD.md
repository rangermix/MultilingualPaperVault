# Candidate build evidence

Use the actual source commit/tree fingerprint and explicit image tags when building
a candidate. The supported product recipes are `deployment/images/app.Dockerfile`
and `deployment/images/database.Dockerfile`. API, worker, parser and parser-models
share the application image; the former separate parser recipe is removed.
Root `compose.example.yaml` is the
single tracked Compose template and binds build args through `SOURCE_COMMIT` and
`SOURCE_TREE_SHA256`. Existing deployments use their preserved local `compose.yaml`
with their own image pins, hardware settings and optional profiles.

Run regression checks with the template's explicit test/check service in a separate
project, following [tests/README.md](../../tests/README.md). Do not use profile-wide
`up` for this: it also starts default product services. Record build commands,
architecture, dependency/model locks and actual image IDs in a fresh `.agent/tmp/`
directory. `acceptance.py run --kind compose` can capture command evidence; do not
label a build alone as successful startup or inference.

Exercise candidates on a disposable Compose project with fresh volumes. Verify
readiness, PDF processing with the selected model/device, publication/export and
backup/restore. The offline harness generates its temporary overrides from the
root template within its unique run directory. Real provider calls need separate
budget/content authorization. Configure providers through the app; preserve the
managed `provider_config` volume and keep credentials out of build inputs.
Disposable candidate probes leave existing instances alone. For an authorized
update, follow the [installation update guide](../../docs/installation.md#updating-an-existing-instance)
and preserve the inspected project, configuration, image references and volumes.
See [deployment](../../docs/deployment/README.md) and
[dependency evidence](../../docs/ops/dependencies.md).
