# Coding Agent Guide

Read the [product scope](docs/product-baseline.md) and the code and tests relevant
to the task first. Upload, parsing, translation,
editing, publication, export and maintenance already exist. Continue from the
current system. Record source capabilities, executed tests and machine runtime
state separately.

## Communication and judgment

- Use simple, minimal, clear language.
- Prefer bullet point lists.
- Treat both your conclusions and the user's as potentially fallible. Check
  assumptions and prioritize accuracy over agreement or confidence.
- Ask for relevant clarification, context or evidence when information is
  insufficient. Keep answers clear and logically organized.

## Working rules

- Run commands from the Git repository root. Code is in `src/`, runtime resources
  in `res/`, tests and fixtures in `tests/`, deployment inputs in `deployment/`,
  and current documentation in `docs/`. Use `PYTHONPATH=src` for host Python
  module calls.
- Preserve unrelated or unfinished changes. Keep verified commits focused and
  push only to the intended remote when requested. Never force push.
- Use an isolated Compose project for development validation. For an authorized
  update to an existing instance, confirm its project, configuration, images and
  persistent volumes before deployment. Preserve settings and data, then check
  health and the changed feature.
- `compose.example.yaml` is the only tracked Compose template. Parsing uses DMR
  full-page models only. API, worker, parser and model preparation share the
  amd64/arm64 application image. Docker supplies CUDA/Metal backends. Root
  `compose.yaml` is ignored local configuration; preserve its project name, image
  bindings, model settings and local overrides. Inspect the actual target before
  maintaining an instance. Tests and checks must explicitly use the template and
  a separate project. Never start tests with a profile-wide `up` or run test
  cleanup against the user's instance.
- Store logs, screenshots, temporary scripts and run reports in a unique
  `.agent/tmp/` run directory. `.agent/local-data/` holds persistent environment
  state, authorization records and private data; never clean it as temporary
  output. Neither directory is committed. Exclude all of `.agent/` from product
  images.
- Keep documentation aligned with current code. Remove superseded plans and
  duplicate instructions. Historical evidence does not prove current acceptance.
  Resolve old evidence paths through `.agent/relocation.json`.

## Product boundaries

- Accept PDF only. Internal IR, test fixtures and the two controlled seed papers
  are not other import routes. Source text must come from the parser or mechanical
  corrections backed by PDF evidence. Translation models must not rewrite source
  text or generate web pages.
- Use one instance with no accounts, users, workspaces, roles or ACLs. Concurrent
  tabs and workers still require generation, CAS, fencing, leases and idempotency
  protections.
- Deploy through Docker Compose only. The app serves HTTP directly, with no
  built-in reverse proxy. Do not install pip/npm dependencies at runtime. Download
  parser and optional local translation weights to persistent volumes only on
  explicit preparation or use. Pin revision, byte size and SHA-256. Image builds,
  startup and settings reads/saves must not download models.
- Connect the parser only to the model preparation and Docker Model Runner
  networks. Give it no database access or Provider keys. The separate
  `parser-models` service only prepares locked resources and never receives PDFs.
  All active parser choices use DMR full-page inference. Keep actual model ID
  validation; do not substitute standalone host services. Docling/Granite
  inference is removed. Paddle, Xiaomi and TeleOCR are retired. Historical
  records remain readable. Never automatically switch a retired task
  to another model or device.
- Content quality findings are nonblocking. Keep automatic checks, deterministic
  recovery and original-image comparison active. Missing passages, number/formula/
  table differences or missing human review must not block translation, sealing,
  publication or export. Handle execution failures, unsafe paths, corrupt
  resources, outbound authorization and version conflicts according to their
  actual conditions.
- Allow all languages and preserve script/region differences in canonical locales.
  Human review is optional; never fabricate confirmation. Keep authors,
  affiliations, identifiers and references in the original language only when
  explicit metadata evidence supports it. Ambiguous body text remains translatable.

## Configuration, secrets and immutable history

- Manage translation services through application settings. Persist API keys only
  in backend secret files on the `provider_config` volume. Never echo them or put
  them in browser storage, the parser, logs or exports. Do not add host bindings
  for Provider profiles or keys. Saving settings must not run a test. Destination,
  protocol, authentication and model ID must match the confirmed configuration.
  Never automatically switch Provider or model.
- Cost controls are optional and default off for new configurations. Preserve
  existing choices. Represent unknown amounts as `null`. Never automatically
  resend a request whose network outcome is unknown. Default limits are 32768
  input tokens, 8192 output tokens and 2000 body characters per unit. Reset changes
  only these limits.
- Permission for the product to store keys does not authorize agents to read real
  credentials. Test doubles do not prove real services or hardware work.
- Never rewrite installed database migrations, sealed source/translation snapshots
  or published resources in place. Reader template IDs, schema versions and
  third-party model versions are compatibility identifiers, not project releases.
  Register new templates separately. Changing a template must not retranslate.
- Complete and validate immutable publication files before switching the current
  pointer with CAS. Backups, restores and cleanup must use the production
  maintenance lock. Never reset the user's instance with test database cleanup
  or `down --volumes`.

Use [tests/README.md](tests/README.md) for validation. Record commands, source,
environment, results and limits. Static Compose checks do not replace cold starts.
Focused tests do not replace real parsing, model calls or recovery validation.
