#!/opt/vllm-env/bin/python
"""Dispatch only the pinned OXR bundle to its compatible vLLM environment."""

from hashlib import sha256
import os
from pathlib import Path
import re
import sys


OXR_ARTIFACT_ID = 'sha256:f4eb6d8c97a613da815b30328a4df00efe9475b68ba2d84f9990d5a7cccede9b'
OXR_PLUGIN_REVISION = 'c708407f9d2b4df658f2543d9132b62bb7221df4'
OXR_VLLM_VERSION = '0.25.1'
OXR_MODEL_ROOT = Path('/models/bundles/sha256') / OXR_ARTIFACT_ID.removeprefix('sha256:') / 'model'
STANDARD_VLLM = '/opt/vllm-env/bin/vllm'
OXR_VLLM = '/opt/oxr-env/bin/vllm'

# vLLM resolves AutoConfig and other auto_map entries from this local bundle.
# Pin the executable code and the configuration that can select it before
# enabling trust-remote-code. DMR also verifies the full OCI model artifact.
TRUSTED_FILES = {
    'config.json': (2794, '758481181d106aef0a0a22c6059f2ab2a224ec1cba2b2c8d8255cb3ce99a0b24'),
    'configuration_oxr.py': (4183, '79b82be9ab046f095cda04a79b5cba3e0dcb4063759f3c11e39485b2242a2c50'),
    'modeling_oxr.py': (45406, '3c3561057eb1f2ac8bea3da397e0f3ba959abcad9c8ff61a8b7b723f5bf56042'),
    'tokenizer_config.json': (5447, '0e18563d7a30d4d8f8c344410fb256f0c4de7b66146872e5afb01caf7b767372'),
    'preprocessor_config.json': (394, '63ff380d3e424f93e6fbca5cc8e74eeed882e96fd6be2b7728aed308f3ad1513'),
    'chat_template.jinja': (517, '8d6f5059459a1d4d91da3c9e7d17cb19d4544eaa2dc0c07a10b61be3c918e970'),
}


def launch(args, environment, model_root=OXR_MODEL_ROOT):
    if OXR_ARTIFACT_ID not in args and str(model_root) not in args:
        return STANDARD_VLLM, args, environment

    # Docker Model Runner v1.2.8 builds this argv in vllm_config.go and vllm.go.
    # Accept one completion model in the approved bundle, with the resource
    # configuration installed by the parser-models service.
    expected = {'--chat-template': str(model_root / 'chat_template.jinja'),
                '--max-model-len': '16384', '--max-num-seqs': '1',
                '--max-num-batched-tokens': '2048'}
    if (args[:2] != ['serve', str(model_root)]
            or args[-3:] != ['--served-model-name', OXR_ARTIFACT_ID, OXR_ARTIFACT_ID]
            or len(args[2:-3]) % 2):
        raise ValueError('Unexpected OXR DMR launch arguments')
    options = dict(zip(args[2:-3:2], args[3:-3:2], strict=True))
    if (len(options) * 2 != len(args[2:-3]) or set(options) != {*expected, '--uds', '--gpu-memory-utilization'}
            or any(options[key] != value for key, value in expected.items())
            or not re.fullmatch(r'inference-runner-[0-9]+\.sock', options['--uds'])
            or not 0 < float(options['--gpu-memory-utilization']) <= 1):
        raise ValueError('Unexpected OXR DMR runtime configuration')
    for relative, (size, digest) in TRUSTED_FILES.items():
        with (model_root / relative).open('rb') as handle:
            data = handle.read(size + 1)
        if len(data) != size or sha256(data).hexdigest() != digest:
            raise ValueError(f'OXR bundle hash or size mismatch: {relative}')
    return OXR_VLLM, [*args, '--trust-remote-code', '--dtype', 'bfloat16',
        '--attention-config', '{"backend":"TRITON_ATTN"}', '--enforce-eager',
        '--limit-mm-per-prompt', '{"image":1,"video":0}'], {
            # vLLM 0.25.1's V2 worker requires UVA, unavailable with WSL's
            # default unpinned host memory. Keep OXR on the V1 model runner.
            **environment, 'VLLM_USE_V2_MODEL_RUNNER': '0', 'VLLM_PLUGINS': 'oxr',
            # Use the native sampler so warmup does not JIT FlashInfer kernels.
            'VLLM_USE_FLASHINFER_SAMPLER': '0',
            'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}


if __name__ == '__main__':
    try:
        binary, args, environment = launch(sys.argv[1:], os.environ)
    except (OSError, ValueError) as error:
        sys.exit(f'Cannot launch pinned OXR artifact: {error}')
    os.execve(binary, [binary, *args], environment)
