# Docker-managed MLX backend payload

The repository builds a custom `darwin/arm64` payload for Docker Model Runner on
Apple Silicon. DMR starts and manages it; the application does not install or start
a separate host Python server. The final scratch image is a macOS payload, not a
runnable Linux container. The payload requires macOS 15 or later and DMR's arm64
Python 3.12 runtime. It uses the matched vLLM and vLLM Metal 0.33.0 wheels. The
Docker build verifies the hashes in the
[runtime lock](../../deployment/mlx-backend/requirements.lock) and the
[build tooling lock](../../deployment/mlx-backend/build-requirements.lock).
[vLLM Metal 0.33.0 release notes](https://github.com/vllm-project/vllm-metal/releases/tag/v0.33.0)
identify the matching vLLM wheel, whose download tag is `v0.33.0rc3`.

## Build

Start with Docker Model Runner's provisioned macOS Python runtime. Copy it into a
fresh build directory, excluding existing third-party libraries:

```sh
TASK_DIR=".agent/tmp/mlx-backend-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$TASK_DIR/runtime"
cp deployment/mlx-backend/{Dockerfile,requirements.lock,build-requirements.lock,sitecustomize.py} "$TASK_DIR/"
rsync -a --exclude site-packages --exclude __pycache__ --exclude prebuilt --exclude .vllm-metal-version "$HOME/.docker/model-runner/vllm-metal/" "$TASK_DIR/runtime/"
codesign --force --sign - --options 0 "$TASK_DIR/runtime/bin/python3"
docker buildx build --platform darwin/arm64 --progress plain --output "type=oci,dest=$TASK_DIR/backend.oci.tar" -t local/paper-translation-vllm-metal:0.33.0 "$TASK_DIR"
docker load --input "$TASK_DIR/backend.oci.tar"
python3 deployment/mlx-backend/extract_oci.py "$TASK_DIR/backend.oci.tar" "$TASK_DIR/extracted"
```

The signature change affects only the copied interpreter, allowing the payload's
native wheels to load together. All dependency installation happens during image
build. The original Docker runtime and global macOS security settings are preserved.
The initializer enables offline behavior and adds `--gpu-memory-utilization 0.25`
when Model Runner launches the API server without a memory flag. Explicit runtime
flags take precedence. The fraction controls the cache calculation, while total
process RAM also includes model weights, activations, and other allocations.

## Install and validate

Stop new parser/translation work and wait for active inference. Unload only this project's idle model, and back up the
entire existing `~/.docker/model-runner/vllm-metal` directory into a new persistent
`.agent/local-data/` directory. Replace the backend directory with the extracted
payload rather than overlaying old and new packages.

Check the actual engine logs, a real image request through the Compose parser, and
a controlled PDF job. Verify the exact locked model ID and effective configuration. Record the source,
backend image/model IDs and outputs. Status text alone is insufficient because DMR
can retain a cached version label after a payload replacement.

Install the [translation extension](local-translation.md) before the final checks
when using local translation. Every replacement, Docker upgrade or restore requires
fresh proof. The runtime heartbeat checks model/backend availability; it does not
reproduce the installation's inference check.

## Rollback

Keep the exact prior payload and local Compose settings. Stop new work, wait for
inference, unload only the affected model and restore the saved
backend directory. Preserve application volumes and model caches. Verify the restored
backend before enabling work. The application has no native CPU parser fallback.
