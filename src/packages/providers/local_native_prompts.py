"""Model-native text translation formats, without instructions inside the source."""
import json
from pathlib import Path

from packages.translation.languages import canonical_locale
from .contract import ProviderFailure

# Exact language-name table from TranslateGemma's published chat template.
# mlx-community/translategemma-4b-it-4bit, revision
# 5788ec08c047f3f2e17808101b8d9566ac930d58, chat_template.jinja.
TRANSLATEGEMMA_LANGUAGES = json.loads(Path(__file__).with_name('translategemma-languages.json').read_text(encoding='utf-8'))
# is-IS/zh-CN are evaluated report codes; en-US appears in Google's text example;
# fil is the ISO language code for the template's fil-PH entry. Reuse only the
# corresponding name, keeping the requested code in the prompt and task history.
TRANSLATEGEMMA_LANGUAGE_ALIASES = {'is-IS': 'is', 'zh-CN': 'zh-Hans', 'en-US': 'en', 'fil': 'fil-PH'}
PLAMO_LANGUAGES = frozenset('ja en zh-Hans zh-Hant ko ar az be bg bn ca ceb de es et eu fa fr gu he hi hr hu hy id it jv ka kk km lt lv ml mr ms my ne nl pa pl ru si sk sl sr sw ta te th tl ur uz vi'.split())
PLAMO_STOPS = ['<|plamo:tag|>', '<|plamo:bos|>']
TRANSLATEGEMMA_STOPS = ['<end_of_turn>', '<eos>']


def _locale(value, languages, *, source=False, detect=False):
    if source and value in ('auto', 'und', None):
        if detect:
            return None
        raise ProviderFailure('SOURCE_LANGUAGE_REQUIRED', 'not_sent')
    try:
        locale = canonical_locale(value)
    except ValueError:
        raise ProviderFailure('LOCAL_MODEL_CONFIG', 'not_sent') from None
    if locale not in languages:
        raise ProviderFailure('LOCAL_MODEL_CONFIG', 'not_sent')
    return locale


def translategemma(source, unit):
    """Render the supported single-text turn exactly as the native template."""
    languages = {**TRANSLATEGEMMA_LANGUAGES, **{
        code: TRANSLATEGEMMA_LANGUAGES[alias] for code, alias in TRANSLATEGEMMA_LANGUAGE_ALIASES.items()}}
    origin = _locale(unit['source_language'], languages, source=True)
    target = _locale(unit['target_locale'], languages)
    origin_name, target_name = languages[origin], languages[target]
    prompt = ('<bos><start_of_turn>user\n'
        f'You are a professional {origin_name} ({origin}) to {target_name} ({target}) translator. '
        f'Your goal is to accurately convey the meaning and nuances of the original {origin_name} text '
        f'while adhering to {target_name} grammar, vocabulary, and cultural sensitivities.\n'
        f'Produce only the {target_name} translation, without any additional explanations or commentary. '
        f'Please translate the following {origin_name} text into {target_name}:\n\n\n'
        + source.strip() + '<end_of_turn>\n<start_of_turn>model\n')
    # The native template has no glossary, background or system channel.
    return {'prompt': prompt, 'add_special_tokens': False, 'stop': list(TRANSLATEGEMMA_STOPS)}


def _plamo_text(value):
    # This is the published template's control-token rejection. Never let
    # document content become PFML3 structure, or rewrite the source to hide it.
    if '<|plamo:' in value:
        raise ProviderFailure('LOCAL_MODEL_CONFIG', 'not_sent')
    return value


def plamo3(source, unit, glossary, markers):
    """PFML3 context/glossary/input/output, with native source detection."""
    origin = _locale(unit['source_language'], PLAMO_LANGUAGES, source=True, detect=True)
    target = _locale(unit['target_locale'], PLAMO_LANGUAGES)
    prompt = '<|plamo:tag|>dataset<|plamo:msg|>translation'
    if (unit.get('preparation_revision') and not unit.get('preparation_context_omitted')
            and unit.get('preparation_context_mode') != 'terms_only'):
        paper = unit.get('context', {}).get('paper', {})
        background = [entry['text'] for entry in paper.get('summary', [])]
        background += [entry['quote'] for entry in paper.get('evidence', [])]
        if background:
            prompt += '<|plamo:tag|>context<|plamo:msg|>' + _plamo_text('\n\n'.join(dict.fromkeys(background)))
    pairs = []
    for entry in glossary:
        if entry.get('mode', 'preferred') == 'forbidden':
            continue
        target_term = entry['source'] if entry.get('mode') == 'retain' else entry.get('target', '')
        if target_term:
            pairs.append((entry['source'], target_term))
    # Protected atoms already use reversible transport markers. Native glossary
    # pairs request their exact preservation without extra source instructions.
    pairs.extend((marker, marker) for marker in markers)
    if pairs:
        prompt += '<|plamo:tag|>glossary' + ''.join(
            '<|plamo:index|>' + _plamo_text(term) + '<|plamo:item|>' + _plamo_text(translation)
            for term, translation in dict.fromkeys(pairs))
    prompt += '<|plamo:tag|>input'
    if origin is not None:
        prompt += '<|plamo:key|>lang<|plamo:val|>' + origin.lower()
    prompt += '<|plamo:msg|>' + _plamo_text(source)
    prompt += '<|plamo:tag|>output<|plamo:key|>lang<|plamo:val|>' + target.lower() + '<|plamo:msg|>'
    # Native BOS insertion differs from the fully rendered Gemma prompt above.
    return {'prompt': prompt, 'add_special_tokens': True, 'stop': list(PLAMO_STOPS)}
