"""Run inside the pinned CUDA runner image, without a GPU or model weights.

Verifies the actual upstream allocator after the image-build patch, including
hybrid attention padding, rather than reproducing the patch's arithmetic.
"""
from types import SimpleNamespace

import torch
from vllm.v1.core.kv_cache_planning import (
    DefaultKVCacheConfigBuilder,
    _max_memory_usage_bytes_from_groups,
    get_kv_cache_configs,
)
from vllm.v1.kv_cache_interface import FullAttentionSpec, KVCacheGroupSpec, KVCacheLayout, SlidingWindowSpec


cfg = SimpleNamespace(
    model_config=SimpleNamespace(max_model_len=8192, original_max_model_len=8192),
    scheduler_config=SimpleNamespace(max_num_seqs=1, max_num_batched_tokens=2048),
    max_in_flight_tokens=2048,
    cache_config=SimpleNamespace(
        num_gpu_blocks_override=None, enable_extensible_kv_cache=False,
        prefix_cache_retention_interval=None, get_resolved_kv_cache_layout=lambda: KVCacheLayout.BLHNC,
    ),
    attention_config=SimpleNamespace(hisparse_config=None),
    parallel_config=SimpleNamespace(
        tensor_parallel_size=1, decode_context_parallel_size=1, prefill_context_parallel_size=1,
    ),
)
full = FullAttentionSpec(block_size=16, num_kv_heads=4, head_size=128, dtype=torch.float16)
sliding = SlidingWindowSpec(block_size=16, num_kv_heads=4, head_size=128, dtype=torch.float16, sliding_window=4096)
available = 20 * 1024**3


def plan(groups):
    specs = {name: group.kv_cache_spec for group in groups for name in group.layer_names}
    return get_kv_cache_configs(cfg, [specs], [available], groups)[0]


full_groups = [KVCacheGroupSpec(['full.0', 'full.1'], full)]
hybrid_groups = [*full_groups, KVCacheGroupSpec(['sliding.0'], sliding)]
null_page = 2 * full.page_size_bytes
for groups in (full_groups, hybrid_groups):
    required = _max_memory_usage_bytes_from_groups(DefaultKVCacheConfigBuilder(), cfg, groups)
    configured = plan(groups)
    # The groups alias one shared backing allocation.
    allocated = max(tensor.size for tensor in configured.kv_cache_tensors)
    assert allocated == required + null_page, (allocated, required, null_page)
    assert allocated < available // 10
    print({'groups': len(groups), 'required_bytes': required, 'allocated_bytes': allocated,
           'num_blocks': configured.num_blocks})
cfg.scheduler_config.max_num_seqs = 2
assert max(tensor.size for tensor in plan(full_groups).kv_cache_tensors) == available
assert plan([]).num_blocks == 1
print('Pinned vLLM cache allocation checks passed')
