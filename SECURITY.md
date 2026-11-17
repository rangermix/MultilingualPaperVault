# Security

## Deployment boundary

Paper Translation serves one personal library without accounts, passwords, roles,
or per-client permissions. Every client that can reach it can operate the instance
and read its available content. The default Compose binding is loopback. Keep that
binding unless you have deliberately arranged trusted access and any required
authentication/TLS outside the application. There is no built-in reverse proxy.

Request-origin and host checks reduce unwanted browser requests; they are not user
authentication. Do not expose the application directly to an untrusted network.
Parser isolation, nonroot/read-only containers, path/hash checks, and bounded PDF
processing reduce risk but do not make arbitrary PDFs or inference output safe in
every environment. The template confines the parser to an internal bridge
without a host gateway. A relay restricts its model traffic to the configured
Docker Model Runner and resource monitor. Keep custom Compose networks and port
bindings within that boundary.

## Reporting a vulnerability

On GitHub, open the repository's **Security and quality** tab and choose
**Report a vulnerability** if available. Otherwise, ask the maintainer for a
private reporting channel. Keep technical details and confidential data out of
public issues. This repository does not promise a response deadline or a
supported-release security maintenance window.

Include the affected source commit/images, environment, impact, prerequisites,
reproduction steps, and a minimal synthetic proof of concept. Explain whether the
issue crosses the intended local-instance boundary. Share only the minimum data
needed to reproduce it. Avoid testing other people's systems or including live
credentials, private papers, database dumps, or full network captures.

For ordinary bugs and model-quality issues, follow [Contributing](CONTRIBUTING.md)
and [Troubleshooting](docs/troubleshooting.md).

## Credentials and content

- API keys are stored as versioned backend files in the `provider_config` volume.
  They are not returned through the API or intended for browser storage, logs,
  exports, parser mounts, or source control. Existing tasks may retain earlier
  credential revisions; changing the current settings does not rewrite them.
- Standard library backups exclude provider configuration and keys. Configure the
  provider again after restoring to a new host. Protect the original volume and
  any separate credential backup; do not attach them to support reports.
- PDFs, generated page images, extraction receipts, translations, exports, and
  library backups can contain private content. Inspect task logs and receipts
  before sharing them, even when credential fields are redacted.
- Translation sends confirmed text and bounded context to the saved destination.
  Parser page images are sent to the configured Docker-managed inference backend.
  Model preparation downloads selected weights; DOI/title metadata lookup can
  query Crossref separately from translation. Review the configured services and
  their data policies before processing sensitive papers.
- Deletion prevents access through the instance and schedules eligible cleanup.
  It does not recall downloaded exports or erase separately retained backups.

If a credential is exposed, revoke or rotate it with the service, then update the
application configuration. Restarting containers or deleting a public message
does not revoke a key. Do not reset library volumes as a credential-recovery step.

## Maintainer checks

Before distributing an image or release, validate the exact source/image inputs,
dependency and model locks, third-party notices, and current vulnerability scan
results. A package inventory or old scan is not clearance for a new image.
Keep workflow permissions minimal and provider secrets out of untrusted PR jobs.
See [Dependency evidence](docs/ops/dependencies.md) and
[Third-party notices](THIRD_PARTY_NOTICES.md).
