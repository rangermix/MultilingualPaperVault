# Agent workspace

Run commands from the repository root. Code lives in `src/`, runtime assets in
`res/`, current guides in `docs/`, and tests plus their fixtures/build inputs in
`tests/`. Python harness helpers add `src/` to their import path.
Root [`compose.example.yaml`](../compose.example.yaml) is the only tracked Compose
template. Product commands use the preserved local `compose.yaml`; tests/checks
use the template explicitly with their own project and targeted `run` service.
Hardware blocks and optional profiles are documented in the
[deployment guide](../docs/deployment/README.md).

| Directory | Purpose |
| --- | --- |
| `harness/` | Reusable probes, controlled test runners, evidence logging and path resolution |
| `tmp/` | Ignored run logs, screenshots, scratch scripts and archived execution artifacts |
| `local-data/` | Ignored persistent runtime configuration, authorization receipts and virtual disks |

Use a distinct `tmp/` directory for every run. Never clean `local-data/` as scratch.
Use `relocation.json` to resolve paths in older test evidence.
Do not replay instance-specific old scripts against an existing user deployment.

The [harness guide](harness/README.md) explains command capture and optional probes.
See [test instructions](../tests/README.md) for maintained entry points. Product
images exclude `.agent/`.
