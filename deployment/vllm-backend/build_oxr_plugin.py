"""Fetch and check the pinned OXR plugin during the optional image build."""

from hashlib import sha256
from importlib.metadata import distribution, entry_points, version
import json
from pathlib import Path
import sys
from urllib.request import urlopen

from oxr_launch import OXR_ARTIFACT_ID, OXR_PLUGIN_REVISION, OXR_VLLM_VERSION


ROOT = f'https://huggingface.co/SoMarkAI/OXR-1.0/raw/{OXR_PLUGIN_REVISION}'
FILES = {
    'LICENSE': (6588, '4577df88e499926976b390c4ea3992cc91baa9ebac29386f35b557bd3cb4a662'),
    'plugins/vllm/pyproject.toml': (435, 'ab03f77744242a516ce3fa8cc973ac0bddc2af26f90a20ed924d42a7f94a1d76'),
    'plugins/vllm/oxr_vllm/__init__.py': (307, '852b7622ba5695a4984341e90096ac18d0b18c54548e60fa7e97d3cfd7161a27'),
    'plugins/vllm/oxr_vllm/oxr_model.py': (23573, 'b66732cd5f97abed11ec13bc6a6e26fbac89a41d62d3995ad127031a6c92eda1'),
    'plugins/vllm/oxr_vllm/oxr_processor.py': (14360, '3342c264bd901109368639ace12ecf7e9137fcaf29f400a7eba152512c6d0b33'),
}

# vLLM 0.25.1's WSL pin-memory warning runs during torch_utils import.
# Its default log scope imports distributed, which needs torch_utils already
# initialized. Process scope keeps the warning and original memory decision.
WSL_WARNINGS = {
    'vllm/platforms/interface.py': (
        '6fbe3057db1f540bf92c3d09bfbcdb5461f6c2ee70ff4ba069ad319e33d42cbd',
        b'                "This may slow down performance."',
    ),
    'vllm/platforms/cuda.py': (
        '28b91ef5d609af2046f504efcdb72353ed7ca7aae600be580f243777320b0e85',
        b'                    "down performance. Please run `wsl --update`."',
    ),
}


def fetch(root):
    for relative, (size, digest) in FILES.items():
        with urlopen(f'{ROOT}/{relative}', timeout=30) as response:
            data = response.read(size + 1)
        if len(data) != size or sha256(data).hexdigest() != digest:
            raise RuntimeError(f'OXR plugin hash or size mismatch: {relative}')
        path = root / relative.removeprefix('plugins/vllm/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def patch_wsl_warning_scope(vllm):
    for relative, (digest, last_line) in WSL_WARNINGS.items():
        path = vllm.locate_file(relative)
        data = path.read_bytes()
        if sha256(data).hexdigest() != digest or data.count(last_line) != 1:
            raise RuntimeError(f'Pinned vLLM WSL warning source changed: {relative}')
        indent = last_line[:len(last_line) - len(last_line.lstrip())]
        path.write_bytes(data.replace(last_line, last_line + b',\n' + indent + b'scope="process",'))


def verify(destination):
    vllm = distribution('vllm')
    if (vllm.version != OXR_VLLM_VERSION or version('transformers') != '5.13.1'
            or version('torch') != '2.11.0+cu130'):
        raise RuntimeError('OXR dependency versions differ from the pinned runtime')
    patch_wsl_warning_scope(vllm)

    import torch
    from vllm.model_executor.models.registry import ModelRegistry

    if torch.version.cuda != '13.0':
        raise RuntimeError('OXR requires the CUDA 13.0 PyTorch build')
    plugins = tuple(entry_points(group='vllm.general_plugins', name='oxr'))
    if len(plugins) != 1 or plugins[0].value != 'oxr_vllm:register':
        raise RuntimeError('Expected pinned OXR plugin entry point')
    plugins[0].load()()
    if 'OXR' not in ModelRegistry.get_supported_archs():
        raise RuntimeError('OXR architecture registration failed')
    destination.write_text(json.dumps({'oxr': {
        'model_artifact_id': OXR_ARTIFACT_ID,
        'vllm_version': OXR_VLLM_VERSION,
        'plugin_revision': OXR_PLUGIN_REVISION,
    }}), encoding='utf-8')


if __name__ == '__main__':
    action, target = sys.argv[1:]
    {'fetch': fetch, 'verify': verify}[action](Path(target))
