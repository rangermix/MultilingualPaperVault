"""Offline inference and a conservative memory default for Docker Model Runner."""
import os
import sys

server_module = 'vllm.entrypoints.openai.api_server'
memory_flag = '--gpu-memory-utilization'
# Model Runner starts the API server with `python -m`. Leave child processes
# and explicit runtime flags alone, including the local translation allowance.
if (sys.argv[0] == '-m' and '-m' in sys.orig_argv
        and sys.orig_argv[sys.orig_argv.index('-m') + 1] == server_module
        and not any(arg == memory_flag or arg.startswith(memory_flag + '=') for arg in sys.argv[1:])):
    sys.argv.extend([memory_flag, '0.25'])

os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY', '1')
os.environ.setdefault('VLLM_NO_USAGE_STATS', '1')
