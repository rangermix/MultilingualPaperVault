# Runtime resources

Only application inputs belong here. Synthetic PDF/IR corpora are
[test fixtures](../tests/fixtures/README.md) and are excluded from product images.

| Path | Runtime consumer |
| --- | --- |
| `schemas/document-ir.schema.json` | `packages.ir.validator`: render-input syntax, alongside semantic validation |
| `schemas/document-ir-v4.schema.json` | Explicit 4.0 source/render semantics for full-page DMR output; legacy 3.0 remains unchanged |
| `reference/reader-v1.css` | Frozen reader template registered by `packages.templates` |
| `reference/legacy-manifest.json` | `packages.seed.legacy`: controlled seed allowlist and navigation patch |
| `reference/reference-files.sha256.json` | Byte-integrity verification of frozen reader and reference inputs |
| `reference/legacy/source/` | Two original arXiv PDFs with [CC BY 4.0 attribution](reference/legacy-NOTICE.md) |
| `vendor/katex-0.19.1/` | Pinned offline math runtime, MIT license, registry integrity and file hashes for reader-v18 |
| `vendor/katex-0.18.7/` | Frozen math runtime and provenance for reader-v4 through v17 |
| `vendor/reader-fonts/` | Source Han Sans CN variable body font and four JetBrains Mono code-font variants for reader-v18, with OFL notices and pinned byte provenance |

This public source snapshot omits the [optional bilingual adaptations](reference/legacy/ADAPTATIONS_OMITTED.md).
The maintenance `seed-legacy` command reports the omission. The original
papers remain available to upload through the ordinary PDF workflow.
Existing legacy publications use stored artifacts for reading and exporting.

Manifest paths beginning `reference/` are resolved relative to this `res/` directory.
Keep their content hashes and the supplied PDF/CSS bytes unchanged.
Schema and reader identifiers are persisted format/template revisions, independent
of the project's package version. API request and model-output schemas are defined
by their actual Python validators rather than duplicate JSON copies here.
