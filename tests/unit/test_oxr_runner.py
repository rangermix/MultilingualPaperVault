"""CPU tests for the DMR-to-vLLM launch boundary, with no model weights."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from packages.local_models.catalog import artifact


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER_PATH = ROOT / 'deployment/vllm-backend/oxr_launch.py'
SPEC = importlib.util.spec_from_file_location('oxr_launch', LAUNCHER_PATH)
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class OxrRunnerTests(unittest.TestCase):
    def test_launcher_pins_match_parser_artifact(self):
        manifest = json.loads((ROOT / 'deployment/parser-vlm-models.lock.json').read_text(encoding='utf-8'))
        model = next(item for item in manifest['models'] if item['id'] == 'oxr-1.0-v1')
        files = {item['path']: (item['size'], item['sha256']) for item in model['files']}
        self.assertEqual(launcher.OXR_ARTIFACT_ID, artifact(model)['id'])
        self.assertEqual(launcher.OXR_PLUGIN_REVISION, model['revision'])
        for path, pin in launcher.TRUSTED_FILES.items():
            with self.subTest(path=path):
                self.assertEqual(files[path], pin)

    def test_standard_engine_invocation_is_preserved(self):
        for args in (['--version'], ['serve', '/models/ordinary', '--uds', '/tmp/ordinary.sock']):
            with self.subTest(args=args):
                env = {'HF_HUB_OFFLINE': '1'}
                self.assertEqual(launcher.launch(args, env), (launcher.STANDARD_VLLM, args, env))

    def test_oxr_invocation_checks_pins_and_selects_plugin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = b'authored configuration fixture'
            (root / 'config.json').write_bytes(config)
            pins = {'config.json': (len(config), hashlib.sha256(config).hexdigest())}
            digest = launcher.OXR_ARTIFACT_ID
            args = ['serve', str(root), '--uds', 'inference-runner-0.sock',
                    '--chat-template', str(root / 'chat_template.jinja'), '--max-model-len', '16384',
                    '--gpu-memory-utilization', '0.42', '--max-num-seqs', '1',
                    '--max-num-batched-tokens', '2048', '--served-model-name', digest, digest]

            with patch.object(launcher, 'TRUSTED_FILES', pins):
                binary, patched_args, env = launcher.launch(args, {}, root)
                self.assertEqual(binary, launcher.OXR_VLLM)
                self.assertEqual(patched_args[:len(args)], args)
                self.assertIn('--trust-remote-code', patched_args[len(args):])
                self.assertEqual(env['VLLM_PLUGINS'], 'oxr')
                self.assertEqual(env['VLLM_USE_V2_MODEL_RUNNER'], '0')
                self.assertEqual(env['VLLM_USE_FLASHINFER_SAMPLER'], '0')
                self.assertEqual(env['HF_HUB_OFFLINE'], '1')

                wrong_path = [*args]
                wrong_path[1] = '/models/other'
                wrong_alias = [*args[:-1], 'other']
                wrong_socket = [*args[:3], '../inference-runner-0.sock', *args[4:]]
                wrong_template = [*args[:5], str(root / 'other.jinja'), *args[6:]]
                override = [*args[:-3], '--hf-overrides', '{"model_type":"foreign"}', *args[-3:]]
                for invalid in (wrong_path, wrong_alias, wrong_socket, wrong_template, override):
                    with self.subTest(args=invalid), self.assertRaisesRegex(ValueError, 'Unexpected OXR DMR'):
                        launcher.launch(invalid, {}, root)

                (root / 'config.json').write_bytes(b'foreign configuration')
                with self.assertRaisesRegex(ValueError, 'OXR bundle hash or size mismatch'):
                    launcher.launch(args, {}, root)
