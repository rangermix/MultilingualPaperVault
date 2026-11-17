"""Bound the pinned vLLM single-request KV cache at image build time."""
from pathlib import Path


NEEDLE = "        kv_cache_configs.append(\n"
REPLACEMENT = '''        # Reserve one full request plus the shared pool's null block. The
        # extensible cache may shrink this initial capacity after warmup.
        if override is None and projected_groups and vllm_config.scheduler_config.max_num_seqs == 1:
            required_bytes = _max_memory_usage_bytes_from_groups(
                builder, vllm_config, projected_groups
            )
            num_blocks = min(num_blocks, required_bytes // bytes_per_block + 1)
            logger.info("Paper Translation bounded KV cache to %d blocks", num_blocks)
''' + NEEDLE


def patch(path):
    content = path.read_text(encoding='utf-8')
    if content.count(NEEDLE) != 1 or 'Paper Translation bounded KV cache' in content:
        raise RuntimeError('Pinned vLLM cache implementation changed')
    path.write_text(content.replace(NEEDLE, REPLACEMENT), encoding='utf-8')


if __name__ == '__main__':
    patch(Path('/opt/vllm-env/lib/python3.12/site-packages/vllm/v1/core/kv_cache_planning.py'))
