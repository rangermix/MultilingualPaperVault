"""Active full-page DMR parsers and separate, read-only historical identities."""
import os
from typing import Literal

ParserProfile = Literal['surya-ocr-2-v1', 'chandra-ocr-2-v1',
                        'infinity-parser2-pro-v1', 'infinity-parser2-flash-v1',
                        'prokope-4b-eagle-eye-v1', 'oxr-1.0-v1']
SURYA_PROFILE = 'surya-ocr-2-v1'
CHANDRA_PROFILE = 'chandra-ocr-2-v1'
INFINITY_PRO_PROFILE = 'infinity-parser2-pro-v1'
INFINITY_FLASH_PROFILE = 'infinity-parser2-flash-v1'
PROKOPE_PROFILE = 'prokope-4b-eagle-eye-v1'
OXR_PROFILE = 'oxr-1.0-v1'
DEFAULT_PROFILE = SURYA_PROFILE
PARSER_PROFILES = (
    {'id': SURYA_PROFILE, 'label': 'Surya OCR 2', 'devices': ['dmr'],
     'description': '0.65B 全页视觉解析；通过 Docker Model Runner 运行。'},
    {'id': CHANDRA_PROFILE, 'label': 'Chandra OCR 2', 'devices': ['dmr'],
     'description': '4B 全页解析，支持复杂表格、手写与多语种；权重约 10.6 GB。'},
    {'id': INFINITY_PRO_PROFILE, 'label': 'Infinity-Parser2 Pro', 'devices': ['dmr'],
     'description': '35.1B 全页解析；约 70.2 GB 权重，需要足够后端内存。'},
    {'id': INFINITY_FLASH_PROFILE, 'label': 'Infinity-Parser2 Flash', 'devices': ['dmr'],
     'description': '2B 全页解析，输出文字、阅读顺序、表格与公式。'},
    {'id': PROKOPE_PROFILE, 'label': 'ProKope-4B-Eagle-Eye', 'devices': ['dmr'],
     'description': '需要 Hugging Face 模型访问批准和完整文件校验；尚不可执行。'},
    {'id': OXR_PROFILE, 'label': 'OXR-1.0', 'devices': ['dmr'],
     'description': '通过支持 OXR 的 Docker Model Runner 对 PDF 整页进行识别。'},
)
PROFILE_IDS = tuple(row['id'] for row in PARSER_PROFILES)
# Registered preferences are distinct from executable parser contracts. Keep
# these identities visible without pretending gated/custom backends are ready.
UNAVAILABLE_PROFILES = {
    PROKOPE_PROFILE: {'code': 'PARSER_MODEL_ACCESS_REQUIRED',
        'model_id': 'ProKope-AI/ProKope-4B-Eagle-Eye',
        'revision': '71ed9e9d53d17b71000d5873bf293da99d55fd52'},
}
VLM_PROFILES = DMR_PROFILES = tuple(p for p in PROFILE_IDS if p not in UNAVAILABLE_PROFILES)
RETIRED_PROFILES = {
    'docling-v1': {'label': 'Docling 标准', 'status': 'removed'},
    'granite-docling-v1': {'label': 'Granite Docling 258M', 'status': 'removed'},
    'paddleocr-vl-1.6-v1': {'label': 'PaddleOCR-VL-1.6', 'status': 'archived'},
    'xiaomi-ocr-0-v1': {'label': 'Xiaomi-OCR-0', 'status': 'archived'},
    'teleocr-v1': {'label': 'TeleOCR', 'status': 'archived'},
}


def recorded_profile(snapshot):
    """Missing old job choices mean the former default, never today's default."""
    value = snapshot.get('parser_profile_revision', 'docling-v1')
    if value not in PROFILE_IDS and value not in RETIRED_PROFILES:
        raise ValueError('PARSER_PROFILE_INVALID')
    return value


def selected_profile(profile):
    value = profile.get('parser_profile_revision', DEFAULT_PROFILE)
    if value in RETIRED_PROFILES:
        raise ValueError('PARSER_PROFILE_UNAVAILABLE')
    if value not in PROFILE_IDS:
        raise ValueError('PARSER_PROFILE_INVALID')
    return value


def unavailable_code(profile, backend=None):
    if profile in UNAVAILABLE_PROFILES:
        return UNAVAILABLE_PROFILES[profile]['code']
    if profile == OXR_PROFILE:
        backend = backend or os.environ.get('PARSER_DMR_BACKEND', 'vllm')
        if backend != 'vllm' or os.environ.get('PARSER_DMR_OXR') != '1':
            return 'PARSER_MODEL_PLUGIN_REQUIRED'
    return None


def available_profiles(backend=None):
    return tuple(profile for profile in DMR_PROFILES if not unavailable_code(profile, backend))


def require_available_profile(profile, backend=None):
    selected_profile({'parser_profile_revision': profile})
    code = unavailable_code(profile, backend)
    if code:
        raise ValueError(code)
    return profile


def preferred_profile(preferences):
    """Reading saved settings preserves inactive choices without enabling them."""
    return recorded_profile(preferences) if 'parser_profile_revision' in preferences else DEFAULT_PROFILE
