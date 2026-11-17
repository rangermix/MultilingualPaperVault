# Full-page parsing through Docker Model Runner

Surya OCR 2 is the default for new preferences. All executable options process a
complete rendered PDF page through Docker Model Runner (DMR):

| Parser | Pinned weights | Download size (decimal GB) | Output contract |
| --- | --- | --- | --- |
| Surya OCR 2 | `datalab-to/surya-ocr-2` | 1.37 | Layout HTML; normalized block rectangles |
| Chandra OCR 2 | `datalab-to/chandra-ocr-2` | 10.61 | Layout HTML; normalized block rectangles |
| Infinity-Parser2 Pro | `infly/Infinity-Parser2-Pro` | 70.23 | Layout JSON; normalized block rectangles |
| Infinity-Parser2 Flash | `infly/Infinity-Parser2-Flash` | 4.45 | Layout JSON; normalized block rectangles |
| OXR-1.0 | `SoMarkAI/OXR-1.0` | 3.08 | Whole-page Markdown with page extent provenance |

The selected revisions, byte counts, hashes, licenses and exact DMR artifact IDs
are in [`parser-vlm-models.lock.json`](../../deployment/parser-vlm-models.lock.json).
Sizes describe downloads, not inference RAM/VRAM. Surya/Chandra have upstream
OpenRAIL terms; Infinity declares Apache 2.0. Inspect those terms before redistribution.

## OXR on the managed CUDA Runner

OXR (`oxr-1.0-v1`) uses the optional Linux/WSL2 CUDA image target `oxr`.
Use these settings in the local Compose environment.

```dotenv
PARSER_DMR_BACKEND=vllm
PARSER_DMR_URL=http://vllm-runner:12434
LOCAL_VLLM_RUNNER_TARGET=oxr
PARSER_DMR_OXR=1
```

Merge the corresponding environment and build target fields from the template
into an existing `compose.yaml`. Build `app` and `vllm-runner` and start the
managed Runner with the `local-vllm` profile. The OXR image adds a separate
vLLM 0.25.1 and Transformers 5.13.1 environment for the exact pinned OXR
artifact. The image patches two startup logging calls in the pinned vLLM wheel
to allow WSL platform detection. OXR uses the V1 model runner and native sampler
to support WSL's default host-memory settings and avoid FlashInfer JIT at warmup.
Other models use the standard vLLM 0.34.0 environment.
Both use the same DMR service, model store and resource inventory.

The private capability endpoint on port 12435 reports the installed OXR plugin
revision, vLLM version and supported artifact. Preparation and inference verify
those values. When the capability is missing, Settings reports that the CUDA
plugin is required. Select OXR and use **准备解析模型** to download its 14 pinned
model files for the first time. The plugin code is verified during image build.
The model uses a custom Apache-derived license. [Plugin source](https://huggingface.co/SoMarkAI/OXR-1.0/tree/c708407f9d2b4df658f2543d9132b62bb7221df4/plugins/vllm).

The product sends each complete page through the upstream whole-page recognition
prompt. The output decoder retains the response and its recognized Markdown
structure. Blocks use the actual PDF page extent as provenance. Word-level
boxes require separate model evidence. The upstream layout and crop
pipeline is a distinct inference route with separate benchmark results.
[Whole-page recognition client](https://github.com/SoMarkAI/OXR/blob/c1a1dcb312ee9f691404f127785510453c0d9350/oxr/model/client.py).

## ProKope access

ProKope is listed as unavailable. The registered model revision is
`71ed9e9d53d17b71000d5873bf293da99d55fd52`. Hugging Face access requires the model
authors' approval. Required configuration bytes are needed for a complete
SHA-256 manifest and resource estimates. The pinned model emits mixed Markdown
and HTML tables after autocontrast and a 1024×768 resize. It needs a bounded
decoder that can use page extent provenance. [Pinned model card](https://huggingface.co/ProKope-AI/ProKope-4B-Eagle-Eye/blob/71ed9e9d53d17b71000d5873bf293da99d55fd52/README.md).

Registration, immutable file hashes, CPU tests and UI tests do not establish real
model inference, quality or speed.

## Shared application image and backend

API, worker, parser, preparation and the relay share one amd64/arm64 application image. It
contains PDF inspection/rendering and model-output conversion, without weights,
Torch, Transformers, Paddle, Docling, ONNX or a CUDA inference runtime. PostgreSQL
and Docker's inference engine are separate images/processes.

Set `PARSER_DMR_BACKEND=vllm` for a compatible Linux/WSL2 Docker-managed backend,
or `mlx` for a compatible Apple Silicon Metal backend. `PARSER_DMR_URL` defaults
to `http://model-runner.docker.internal`; a Docker-managed runner with model,
configuration and inference APIs may use an explicit URL. Engine status text
establishes availability, not the engine's actual version or model/image support.

The independently pinned Infinity SDK requires vLLM >=0.26, while its pinned model
cards demonstrate 0.17.1. The standard runner's 0.34.0 meets the SDK's version
requirement. Model and image request compatibility still need an inference check.
Select and verify a Docker-managed engine that supports the exact model and image
request. Metal uses a different version scheme. Portable client builds do not
certify a hardware/backend combination. See
[Docker inference engines](https://docs.docker.com/ai/model-runner/inference-engines/)
and [Metal payload setup](mlx-backend.md).

For a new deployment copy the [template](../../compose.example.yaml), configure
DMR, then run:

```sh
cp compose.example.yaml compose.yaml
docker compose build app parser db
docker compose up -d --wait
```

For an existing instance, merge the service/network/cache changes into its ignored
local Compose file while preserving its project name, image pins, backend overrides
and data volumes. A rebuild cannot add missing mounts or services.

## On-demand preparation and isolated execution

Images contain no parser weights. Explicit **准备解析模型** in Settings or first
parsing use downloads only the selected pinned files. Startup and settings reads
or saves do not download or infer. The preparation service owns the writable
`parser_models` cache and receives no PDF, database or translation credential.
The parser mounts the cache read-only. Its internal `parser_inference` bridge
has no host gateway and carries requests to `parser-models` and `parser-dmr`.
The relay forwards the parser's model API calls and read-only telemetry to the
operator-configured upstreams over `model_inference`. The app and worker reach
`parser-models` on `parser_model_control`.

When upgrading a local Compose file, merge the new `parser-dmr` service and
network declarations before recreating the parser. Set the parser's effective
network list to just `parser_inference`, including when it inherits anchors or
overrides. Move custom DMR and resource-monitor URLs to `parser-dmr` and
`parser-models`. Leave the parser's two internal relay URLs as defined by the
template. The managed Runner remains on `model_inference`.

Preparation streams verified files into Docker's OCI model store. Before image
inference the client rechecks the exact artifact ID and effective configuration;
a wrong model/backend fails instead of switching. The cache and DMR each retain a
copy: allow about twice the download size on disk (about 141 GB for Pro), plus
working space and backend memory. Library backups exclude re-downloadable caches.

DMR restricts engine startup flags. The parser sends thinking controls through
each inference request's `chat_template_kwargs`, without adding the rejected
`--default-chat-template-kwargs` startup flag. A rejected configuration now reports
`PARSER_DMR_CONFIGURATION_FAILED`; already verified cached weights can be reused
on the next explicit preparation. Preparation readiness verifies files, imported
identity and configuration, but does not establish successful image inference.

One PDF runs at a time with bounded child resources, deadlines and fence checks.
The parser's 16 GiB cgroup limit applies to its PDF/client work, not Docker's backend
VRAM or Metal process. Cancellation prevents late commits; already submitted
inference may finish. No CPU/CUDA inference framework is installed at runtime.

## Memory budgets and concurrency

Settings → **资源与并发** controls shared RAM/VRAM admission budgets (80% by
default), simultaneous main operations (default 2), and units per operation
(default 1). Auto mode reduces those ceilings using remaining RAM/VRAM; all modes
check the model estimate against measured usage before dispatch. A resident model
is charged once, and pending loads reserve their estimated allocation. Waiting
does not consume an attempt. Existing requests finish when a limit is lowered.
The parser remains serial; llama.cpp can serve concurrent units using its shared
context/cache. Model loading waits for active local requests to finish. The
worker's global ceiling is 16; backend slot limits may be lower.
Explicit model preparation uses this queue too. Existing local Compose files
must include `parser_model_control` in the worker's networks, as in the template,
so an admitted preparation can reach `parser-models`.

The managed CUDA Runner exposes private read-only telemetry on port 12435 inside
`model_inference`, with no host port or Docker socket. Rebuild both the application
image and `deployment/vllm-backend` when updating an existing CUDA instance. RAM
is the memory visible to Docker's Linux host/VM, not Windows Task Manager's total;
VRAM is GPU 0, including other processes. Missing GPU telemetry holds local CUDA
work in the queue. External/native runners need equivalent capacity telemetry
configured through `RESOURCE_MONITOR_URL` in the Compose environment for
`parser-dmr` and `parser-models` before automatic GPU admission is available. MLX references count unified memory once;
Linux VM RAM telemetry does not measure a native macOS Metal process.

These are admission budgets with estimated headroom, not OS-enforced quotas or
guarantees against other programs allocating memory after a sample. Existing
container cgroup limits still apply independently. Estimates in Settings use
locked weight sizes, full configured context and working-space allowances; they
are deliberately labelled estimates rather than measured peaks.

The pinned CUDA vLLM 0.34.0 standard environment bounds its single-request KV allocation using
vLLM's own attention-group calculation: one full context plus a null block.
The image build fails if the expected upstream implementation changes. Parser
startup also requests a model-sized fraction of device memory instead of an
independent 80% for every model. This removes the unused full-device cache
reservation while keeping model identity, quantization and context unchanged.

## Retired choices and immutable history

Docling and Granite inference have been removed. PaddleOCR-VL, Xiaomi and
TeleOCR are retired parser choices.

Existing saved IDs, queued snapshots, source revisions and published readers are
not reassigned or rewritten. Settings displays retired choices as inactive; select
an active parser explicitly for new work. A queued retired/native task fails with
an actionable unavailable-parser result. Existing source remains usable for
translation, reading and export without re-parsing.

Shared PDF recovery and nonblocking quality checks remain active. See the
[architecture guide](../architecture.md) for the full-page model output contract.
Source capability, offline regression results and actual model/hardware evidence
must be recorded separately. No live inference claim follows from a build or test double.
