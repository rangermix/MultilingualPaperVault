"""Reviewed target-language metadata for the pinned translation model families.

This is selector metadata, not a global locale policy or an inference-quality
guarantee. Keep it outside model artifacts and frozen Provider profiles.
"""

# Use the explicit supported-language table, rather than the Hy-MT2 card's
# inconsistent headline count. Chinese is represented with both script choices.
# https://huggingface.co/tencent/Hy-MT2-1.8B/blob/9a341cd1b679d3efd23b46e847b01745a71ed792/README.md#supported-languages
_HY = tuple('zh-Hans en fr pt es ja tr ru ar ko th it de vi ms id tl hi zh-Hant pl cs nl km my fa gu ur te mr he bn ta uk bo kk mn ug yue'.split())

# All three v0.1 sizes declare the same 46 languages; those are the base models
# of the catalog's GGUF/MLX conversions, not a newer model replacement.
# https://huggingface.co/xiaomi-research/MiLMMT-46-1B-v0.1
# https://huggingface.co/xiaomi-research/MiLMMT-46-4B-v0.1
# https://huggingface.co/xiaomi-research/MiLMMT-46-12B-v0.1
_MILMMT = tuple('ar az bg bn ca cs da de el en es fa fi fr he hi hr hu id it ja kk km ko lo ms my no nl pl pt ro ru sk sl sv ta th tl tr ur uz vi yue zh-Hans zh-Hant'.split())

# TranslateGemma's report evaluates 55 target locales (50 base languages),
# plus English as the source. Preserve evaluated regional distinctions and use
# canonical Chinese script tags. This is narrower than its template-name table.
# https://arxiv.org/abs/2601.09012 (Table 4)
# https://huggingface.co/google/translategemma-4b-it
_TRANSLATEGEMMA = tuple('en ar-EG ar-SA bg-BG bn-IN ca-ES cs-CZ da-DK de-DE el-GR es-MX et-EE fa-IR fi-FI fil-PH fr-CA fr-FR gu-IN he-IL hi-IN hr-HR hu-HU id-ID is-IS it-IT ja-JP kn-IN ko-KR lt-LT lv-LV ml-IN mr-IN nl-NL no-NO pa-IN pl-PL pt-BR pt-PT ro-RO ru-RU sk-SK sl-SI sr-RS sv-SE sw-KE sw-TZ ta-IN te-IN th-TH tr-TR uk-UA ur-PK vi-VN zh-Hans zh-Hant zu-ZA'.split())

# PFNet's native PFML3 language codes, common to 0.8B/2B/8B/31B.
# https://huggingface.co/pfnet/plamo-3-translate-2b#supported-languages
_PLAMO3 = tuple('ja en zh-Hans zh-Hant ko ar az be bg bn ca ceb de es et eu fa fr gu he hi hr hu hy id it jv ka kk km lt lv ml mr ms my ne nl pa pl ru si sk sl sr sw ta te th tl ur uz vi'.split())

_TARGET_LANGUAGES = {'hy': _HY, 'milmmt': _MILMMT,
                     'translategemma': _TRANSLATEGEMMA, 'plamo3': _PLAMO3}


def target_language_match(model):
    """Native code-based models cannot inherit arbitrary regional selectors."""
    return 'exact' if model.get('family') in ('translategemma', 'plamo3') else 'language'


def supported_target_languages(model):
    """Return a fresh list, or unknown for models without a reviewed declaration."""
    if model.get('purpose', 'translation') != 'translation':
        return None
    languages = _TARGET_LANGUAGES.get(model.get('family'))
    return list(languages) if languages is not None else None
