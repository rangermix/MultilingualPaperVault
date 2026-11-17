import { afterEach, describe, expect, it, vi } from 'vitest';
import ts from '@typescript/typescript6';
import { getUiLocale, messages, resolveUiLocale, setUiLocale, t, uiLocales } from './i18n';
import { statusLabel } from './domain';
import { errorMessage, issueMessage } from './messages';
import { localizeBootstrap } from './bootstrap-i18n';
import { coreMessages } from './locales/core';
import { settingsMessages } from './locales/settings';
import { workflowMessages } from './locales/workflow';
import { editorMessages } from './locales/editor';
import { auditMessages } from './locales/audit';
import { extendedMessages } from './locales/extended';

const expectedLocales = ['zh-Hans', 'zh-Hant', 'en', 'ja', 'cs', 'da', 'de', 'es', 'fr', 'id', 'it', 'hu', 'nl', 'pl', 'pt', 'ro', 'tr', 'ru', 'uk', 'ar'];
afterEach(() => { vi.unstubAllGlobals(); setUiLocale('zh-Hans'); });
describe('interface language', () => {
  it('offers exactly the same 20 interface languages as TwitchDropsMiner', () => {
    expect(uiLocales.map(locale => locale.value)).toEqual(expectedLocales);
    expect(new Set(uiLocales.map(locale => locale.label)).size).toBe(20);
    expect(Object.keys(extendedMessages)).toEqual(expectedLocales.slice(3));
  });
  it('resolves script and region while respecting the browser preference order', () => {
    expect(resolveUiLocale(['zh-TW'])).toBe('zh-Hant');
    expect(resolveUiLocale(['zh-HK'])).toBe('zh-Hant');
    expect(resolveUiLocale(['zh-Hans-TW'])).toBe('zh-Hans');
    expect(resolveUiLocale(['zh-CN'])).toBe('zh-Hans');
    expect(resolveUiLocale(['zh-MO'])).toBe('zh-Hant');
    expect(resolveUiLocale(['zh-Hant-CN'])).toBe('zh-Hant');
    expect(resolveUiLocale(['zh-SG'])).toBe('zh-Hans');
    expect(resolveUiLocale(['en-AU', 'zh-Hant'])).toBe('en');
    expect(resolveUiLocale(['fr-CA', 'zh-Hant'])).toBe('fr');
    expect(resolveUiLocale(['ko-KR', 'uk-UA', 'en'])).toBe('uk');
    expect(resolveUiLocale(['invalid_!', 'de-AT'])).toBe('de');
    expect(resolveUiLocale(['ko-KR', 'invalid_!'])).toBe('en');
    expect(resolveUiLocale([])).toBe('en');
    for (const [language, region] of Object.entries({ ja: 'JP', cs: 'CZ', da: 'DK', de: 'DE', es: 'MX', fr: 'FR', id: 'ID', it: 'IT', hu: 'HU', nl: 'BE', pl: 'PL', pt: 'BR', ro: 'RO', tr: 'TR', ru: 'RU', uk: 'UA', ar: 'EG' })) {
      expect(resolveUiLocale([`${language}-${region}`])).toBe(language);
    }
  });
  it('switches display-time status and error maps without changing their identifiers', () => {
    setUiLocale('en');
    expect(statusLabel('queued')).toBe('Queued');
    expect(errorMessage('BUDGET_REQUIRED')).toMatch(/budget/i);
    expect(errorMessage('UNKNOWN_BACKEND', '无法识别的原始诊断')).toBe('The operation did not complete. Review the technical details or try again later.');
    setUiLocale('zh-Hant');
    expect(statusLabel('queued')).toBe('排隊中');
    expect(t('界面语言')).toBe('介面語言');
    expect(getUiLocale()).toBe('zh-Hant');
  });
  it('interpolates only named values once and preserves their contents', () => {
    const evidence = '<b>设置</b> {id} $& C:\\paper\\<source>.pdf';
    for (const { value: locale } of uiLocales) {
      setUiLocale(locale);
      const template = t('跳转段落 {id}');
      expect(t('跳转段落 {id}', { id: evidence })).toBe(template.replace('{id}', () => evidence));
      expect(t('unregistered {value}', { value: 0 })).toBe('unregistered 0');
      expect(t('unregistered {missing}', {})).toBe('unregistered {missing}');
      expect(t('unregistered {id}', Object.create({ id: 'inherited value' }))).toBe('unregistered {id}');
      expect(t('toString')).toBe('toString');
      expect(t('__proto__')).toBe('__proto__');
      expect(t({ key: 'unregistered {id}', values: { id: evidence } })).toBe(`unregistered ${evidence}`);
    }
  });
  it('reads each additional catalogue at display time without changing source identifiers', () => {
    const source = '界面语言';
    for (const [locale, catalog] of Object.entries(extendedMessages)) {
      setUiLocale(locale as keyof typeof extendedMessages);
      expect(t(source)).toBe(catalog[messages[source][0]]);
      expect(statusLabel('queued')).toBe(catalog[messages['排队中'][0]]);
    }
  });
  it('localizes authored source diagnostics and preserves model explanations and evidence', () => {
    const issue = { stage: 'source_check', category: 'page_missing', page: 2, severity: 'important', message: '第 2 页文字未完整提取' };
    setUiLocale('en'); expect(issueMessage(issue)).toBe('Text on page 2 was not fully extracted');
    expect(issueMessage({ stage: 'translation', severity: 'important', code: 'NUMBER_MISMATCH', message: '译文中的数字与原文存在差异，可查看原 PDF 对照。' })).toContain('Numbers differ');
    setUiLocale('zh-Hant'); expect(issueMessage(issue)).toBe('第 2 頁文字未完整擷取');
    expect(issueMessage({ stage: 'semantic_review', severity: 'info', message: '设置 <paper> body' })).toBe('设置 <paper> body');
    expect(issue.message).toBe('第 2 页文字未完整提取');
  });
  it('builds the no-JavaScript notice in all 20 languages with the matching direction', () => {
    const page = localizeBootstrap('<title><!--app-title--></title><noscript><!--app-noscript--></noscript>');
    expect(page).toContain('<title>Bilingual Library · Personal PDF library</title>');
    expect(page).toContain('<p lang="en" dir="ltr">The management interface requires JavaScript.');
    expect(page).toContain('<p lang="zh-Hans" dir="ltr">管理界面需要 JavaScript。');
    expect(page).toContain('<p lang="zh-Hant" dir="ltr">管理介面需要 JavaScript。');
    expect([...page.matchAll(/<p lang="([^"]+)" dir="(ltr|rtl)">([^<]+)<\/p>/g)].map(([, locale, dir, text]) => ({ locale, dir, populated: text.length > 0 })))
      .toEqual(expectedLocales.map(locale => ({ locale, dir: locale === 'ar' ? 'rtl' : 'ltr', populated: true })));
    expect(page).not.toContain('<!--app-');
  });
  it('keeps every catalogue translation and interpolation complete', () => {
    const keys = [coreMessages, settingsMessages, workflowMessages, editorMessages, auditMessages].flatMap(catalog => Object.keys(catalog));
    expect(new Set(keys).size, 'Shared messages must be declared only in core.ts').toBe(keys.length);
    const placeholders = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();
    for (const [source, translations] of Object.entries(messages)) {
      for (const translation of translations) {
        expect(translation.trim(), source).not.toBe('');
        expect(placeholders(translation), source).toEqual(placeholders(source));
      }
    }
    const englishKeys = [...new Set(Object.values(messages).map(entry => entry[0]))].sort();
    for (const [locale, catalog] of Object.entries(extendedMessages)) {
      expect(Object.keys(catalog).sort(), `${locale}: exact authored message coverage`).toEqual(englishKeys);
      for (const [source, [english]] of Object.entries(messages)) {
        const translation = catalog[english];
        expect(typeof translation, `${locale}: ${source}`).toBe('string');
        expect(translation.trim(), `${locale}: ${source}`).not.toBe('');
        expect(placeholders(translation), `${locale}: ${source}`).toEqual(placeholders(source));
      }
    }
  });
  it('registers every explicit UI message for all catalogue translations', () => {
    const files = import.meta.glob(['./**/*.ts', './**/*.tsx', '!./**/*.test.ts', '!./locales/**'], { query: '?raw', import: 'default', eager: true });
    const missing: string[] = [];
    for (const [path, source] of Object.entries(files)) {
      const ast = ts.createSourceFile(path, source as string, ts.ScriptTarget.Latest, true, path.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
      function visit(node: ts.Node) {
        if ((ts.isCallExpression(node) || ts.isNewExpression(node)) && ts.isIdentifier(node.expression) && ['t', 'uiMessage', 'UiError'].includes(node.expression.text)) {
          const key = node.arguments?.[0];
          if (key && ts.isStringLiteralLike(key) && !Object.hasOwn(messages, key.text)) missing.push(`${path}: ${key.text}`);
        }
        ts.forEachChild(node, visit);
      }
      visit(ast);
    }
    expect(missing).toEqual([]);
  });
  it('stores only the browser locale and responds to same-origin localStorage changes', async () => {
    const storage = { getItem: vi.fn(() => 'ar'), setItem: vi.fn() };
    let storageListener: ((event: StorageEvent) => void) | undefined;
    vi.stubGlobal('localStorage', storage);
    vi.stubGlobal('navigator', { languages: ['ja-JP'], language: 'ja-JP' });
    vi.stubGlobal('window', { addEventListener: (type: string, listener: (event: StorageEvent) => void) => { if (type === 'storage') storageListener = listener; } });
    vi.resetModules();
    const instance = await import('./i18n');
    expect(instance.getUiLocale()).toBe('ar');
    expect(storage.getItem).toHaveBeenCalledWith(instance.uiLocaleStorageKey);
    instance.setUiLocale('uk');
    expect(storage.setItem).toHaveBeenCalledExactlyOnceWith(instance.uiLocaleStorageKey, 'uk');
    expect(instance.getUiLocale()).toBe('uk');
    const event = (newValue: string | null, overrides: Partial<StorageEvent> = {}) => storageListener!({ key: instance.uiLocaleStorageKey, newValue, storageArea: storage, ...overrides } as StorageEvent);
    event('tr', { storageArea: {} as Storage });
    event('tr', { key: 'unrelated-setting' });
    expect(instance.getUiLocale()).toBe('uk');
    event('tr');
    expect(instance.getUiLocale()).toBe('tr');
    event('unsupported');
    expect(instance.getUiLocale()).toBe('ja');
    event('fr');
    event(null, { key: null });
    expect(instance.getUiLocale()).toBe('ja');
    expect(storage.setItem).toHaveBeenCalledTimes(1);
  });
  it('keeps an in-memory choice when browser storage is unavailable', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    vi.stubGlobal('navigator', { languages: ['pt-PT'], language: 'pt-PT' });
    vi.stubGlobal('window', { addEventListener: () => {} });
    vi.resetModules();
    const instance = await import('./i18n');
    expect(instance.getUiLocale()).toBe('pt');
    instance.setUiLocale('ar');
    expect(instance.getUiLocale()).toBe('ar');
  });
});
