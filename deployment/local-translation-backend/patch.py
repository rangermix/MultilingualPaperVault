"""Build-time patch, fail closed if the pinned backend layout changes."""
import importlib.util
import json
from pathlib import Path
from textwrap import dedent, indent

root = Path('/vllm-metal/lib/python3.12/site-packages')

adapter = root / 'vllm_metal/v1/model_adapter.py'
source = adapter.read_text()
model_type = '        model_type_from_hf = hf_config.model_type\n'
override = '        if model_type_from_hf in '
anchors = (
    model_type + override + '_TEXT_BACKBONE_OVERRIDE_MODEL_TYPES:',  # Metal 0.33
    model_type + override + '_TEXT_BACKBONE_OVERRIDE_TYPES:',        # Metal 0.29
)
matches = [anchor for anchor in anchors if anchor in source]
assert len(matches) == 1 and source.count(matches[0]) == 1, (
    'Backend adapter changed; review the MLX text-loader patch.'
)
anchor = matches[0]
gemma_override = (
    '        if model_type_from_hf == "gemma3" and self._has_mlx_quantized_weights(hf_config):\n'
    '            return True\n'
)
adapter.write_text(source.replace(anchor, anchor.replace(model_type, model_type + gemma_override)))
spec = importlib.util.spec_from_file_location('catalog', '/catalog/catalog.py')
catalog = importlib.util.module_from_spec(spec); spec.loader.exec_module(catalog)
(root / 'translation_model_ids.json').write_text(json.dumps([
    catalog.artifact(m)['id'] for m in catalog.models() if m['runtime'] == 'mlx']))
startup = root / 'sitecustomize.py'
startup.write_text(startup.read_text() + '\nimport translation_startup\n')
cache = root / 'vllm_metal/v1/cache_policy.py'
source = cache.read_text()
anchors = {
    '        if explicit is None:\n            kv_budget -= kv_offload_pool\n': ' ' * 12,  # Metal 0.33
    '        kv_budget = base_kv_budget - reservation.total_bytes - draft_scratch_bytes\n': ' ' * 8,  # Metal 0.29
}
matches = [anchor for anchor in anchors if anchor in source]
assert len(matches) == 1 and source.count(matches[0]) == 1, (
    'Backend cache planner changed; review bounded allocation.'
)
# Apply the cap after the host-pool reservation and before the physical commit
# probe. Metal 0.33 applies this only to its automatically calculated budget.
anchor = matches[0]
cap = dedent('''\
    from translation_startup import bounded_cache_budget
    kv_budget = bounded_cache_budget(
        self._worker.model_config.served_model_name, self._worker.model_config.max_model_len,
        block_size, per_block_bytes, kv_budget,
    )
''')
cache.write_text(source.replace(anchor, anchor + indent(cap, anchors[anchor])))
