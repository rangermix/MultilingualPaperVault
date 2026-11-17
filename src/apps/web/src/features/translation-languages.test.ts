import { describe, expect, it } from 'vitest';
import { supportsTargetLanguage } from './translation-languages';

describe('declared translation language support', () => {
  it('keeps unknown custom API model support open without accepting invalid tags', () => {
    expect(supportsTargetLanguage('pt-BR', null)).toBe(true);
    expect(supportsTargetLanguage('fil', undefined)).toBe(true);
    expect(supportsTargetLanguage('invalid_!')).toBe(false);
  });
  it('keeps region and script variants without changing the saved tag', () => {
    expect(supportsTargetLanguage('pt-BR', ['pt'])).toBe(true);
    expect(supportsTargetLanguage('sr-Latn-RS', ['sr'])).toBe(true);
    expect(supportsTargetLanguage('de', ['pt'])).toBe(false);
    expect(supportsTargetLanguage('en', [])).toBe(false);
  });
  it('matches declared Chinese scripts and Filipino aliases', () => {
    expect(supportsTargetLanguage('zh-TW', ['zh-Hant'])).toBe(true);
    expect(supportsTargetLanguage('zh-Hans-TW', ['zh-Hant'])).toBe(false);
    expect(supportsTargetLanguage('zh-CN', ['zh-Hans', 'zh-Hant'])).toBe(true);
    expect(supportsTargetLanguage('tl-PH', ['fil'])).toBe(true);
    expect(supportsTargetLanguage('fil', ['tl'])).toBe(true);
  });
  it('requires a declared canonical locale for native translation models', () => {
    expect(supportsTargetLanguage('EN-us', ['en-US'], 'exact')).toBe(true);
    expect(supportsTargetLanguage('cs-CZ', ['cs-CZ'], 'exact')).toBe(true);
    expect(supportsTargetLanguage('cs-CZ', ['cs'], 'exact')).toBe(false);
    expect(supportsTargetLanguage('en-US', ['en'], 'exact')).toBe(false);
    expect(supportsTargetLanguage('en', ['en-US'], 'exact')).toBe(false);
    expect(supportsTargetLanguage('zh-Hans', ['zh-CN'], 'exact')).toBe(false);
    expect(supportsTargetLanguage('zh-TW', ['zh-Hant'], 'exact')).toBe(false);
    expect(supportsTargetLanguage('en', [], 'exact')).toBe(false);
    expect(supportsTargetLanguage('invalid_!', ['en'], 'exact')).toBe(false);
  });
  it('keeps unknown API coverage unrestricted regardless of locale match mode', () => {
    expect(supportsTargetLanguage('pt-BR', null, 'exact')).toBe(true);
    expect(supportsTargetLanguage('zh-Hans-TW', undefined, 'exact')).toBe(true);
  });
});
