# Execution evidence and optional probes

Run from the repository root. The default regression workflow is documented in
[tests/README.md](../../tests/README.md). These tools supplement it with command
records, isolated deployment probes and explicitly authorized model tests.
There is no separate milestone catalog or generated project-completion gate.

## Command records

```sh
python .agent/harness/acceptance.py probe
python .agent/harness/acceptance.py fingerprint
python .agent/harness/acceptance.py run --id focused-tests --kind automated -- python -m pytest -q tests/unit
```

`run` records the arguments, source fingerprint, Git commit/dirty state, environment,
exit status, elapsed time and redacted output. Logs and records use unique names
under `.agent/tmp/evidence/`. A changed source tree makes the run fail. Optional
`--tests` values describe the checks exercised, not entries in a planned registry.
`--full-scenario` is an explicit scope claim and requires actual execution evidence;
static checks cannot claim it. Exit status zero alone does not certify the product.

`blocked` records a concrete missing prerequisite. `review` imports independent,
source-bound findings after file/hash verification; see [review format](AGENT_REVIEW.md).
Fake providers belong to automated evidence, never live-provider evidence. YAML
validation is a static check, never a Compose cold-start result.

Fingerprints include maintained source, tests, fixtures and harness code. They
exclude agent notes/memory/output, dependencies, local Compose/editor settings and
private configuration/secret files without reading their contents. Record selected
runtime configuration separately with redacted evidence. Archived source hashes
are not silently promoted after a path change.

## Explicit probes

Most matrix scripts accept candidate images or target a disposable Compose project.
Read their arguments and target configuration before running them. They can create
containers/volumes, execute native parsers or mutate test data. Historical source
review replays require their exact ignored evidence corpus; absence is not a pass.

- `verify_compose.py`: historical validator for the retired CPU/CUDA/Paddle-MLX
  service layout. Its assertions do not describe the current full-page DMR stack;
  do not use it as current configuration or runtime acceptance. Maintained static
  boundaries are checked by `src/tools/check_package.py` through the `checks` service.
- `offline_compose_roundtrip.py`: fresh-project backup/restore exercise, using
  root `compose.example.yaml`, prepared candidate images and overrides generated
  inside its unique run directory. The candidate image must include the complete
  [legacy seed pack](../../res/reference/legacy/ADAPTATIONS_OMITTED.md).
  This probe uses disposable projects.
- `release_inventory.py`: combines exact image IDs with matching scan/SBOM output
  into a fresh report. Use `--help` for candidate arguments.
- `parser_runtime_dependencies.py`: checks actual dependencies/model assets inside
  the selected parser image. This is inventory, not inference or a vulnerability audit.
- `build_*fixtures.py`: explicit synthetic-fixture generators; not application code.
- `live_provider_run.py`: guarded real-model runner requiring the authorization
  described in [LIVE_PROVIDER.md](LIVE_PROVIDER.md).

For a basic check of an existing local instance, replace `EXISTING_PROJECT` with
its actual Compose project name and use the same configuration inputs as its deployment:

```sh
docker compose -p EXISTING_PROJECT -f compose.yaml config --quiet
docker compose -p EXISTING_PROJECT -f compose.yaml ps
```

Add the instance's original `--env-file`, profile and override options when used.
Compose file and environment options may be repeated in deployment order.
These commands check configuration syntax and reported container state; they do
not validate image identity, all mount/network boundaries or model inference.

Keep credentials, persistent disks, old receipts and evidence intact.

The sole tracked Compose template includes `checks`, `tests`, `maintenance`,
`local-translation` and `local-vllm` profiles. Use explicit service targets for one-off runs; profile
`up` also starts default product services. Routine tests/checks must retain their
separate project names and `-f compose.example.yaml` options from the test guide.
