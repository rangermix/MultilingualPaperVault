import { test, expect, type Page } from '../../src/apps/web/node_modules/@playwright/test/index.mjs';
import { outputDirectory } from './paths';

const firstModel = 'synthetic/translator-a@sha256:fixture';
const secondModel = 'synthetic/translator-b@sha256:fixture';
async function fixture(page: Page, { local = true, locale = 'de', supported = ['en', 'zh-Hans', 'ja'] as string[] | null } = {}) {
  let preferences = { generation: 1, locale, theme: 'light', parser_profile_revision: 'surya-ocr-2-v1' };
  const writes: { path: string; body: unknown }[] = [], errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const model = (id: string, model_id: string, languages: string[]) => ({ id, model_id, label: id, family: 'fixture', family_label: 'Fixture',
    parameter_size: '2B', bits: 4, quantization: 'Q4', format: 'gguf', runtime: 'llama.cpp', repo: 'synthetic/translator', revision: 'fixture',
    download_bytes: 1000, status: 'not_downloaded', supported_target_languages: languages });
  await page.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname.slice(7);
    if (request.method() !== 'GET') {
      writes.push({ path, body: request.postDataJSON() });
      if (path === '/settings/preferences') {
        expect(request.headers()['if-match']).toBe(`"${preferences.generation}"`);
        preferences = { ...preferences, ...request.postDataJSON(), generation: preferences.generation + 1 };
      }
    }
    const profile = { generation: 1, configured: true, dispatch_configuration_ready: true, has_api_key: false, config_source: 'managed',
      provider: local ? 'local' : 'openai', api_protocol: local ? 'local_translation' : 'responses', auth_mode: 'none',
      endpoint: 'https://synthetic.invalid/v1/responses', model_id: local ? firstModel : 'custom-api-model', local_backend: 'llama.cpp',
      cost_control_enabled: false, profile_hash: 'a'.repeat(64), supported_target_languages: supported };
    const values: Record<string, unknown> = {
      '/capabilities': { source_mime_types: ['application/pdf'] }, '/settings/preferences': preferences, '/settings/provider': profile,
      '/settings/dispatch': { generation: 1, dispatch_disabled: false }, '/settings/resources': { waiting_jobs: [], model_references: [] },
      '/settings/parser-environment': { options: [] }, '/settings/parser-models': { models: [] },
      '/settings/local-models': { models: [model('Translator A', firstModel, ['en', 'zh-Hans', 'ja']), model('Translator B', secondModel, ['en', 'de', 'ar'])] },
      '/documents/doc': { id: 'doc', title: 'Original title', generation: 1, tags: [], lifecycle: 'active', source_revision_id: 'source', editions: [] },
      '/imports/import/preflight': { import_id: 'import', document_id: 'doc', generation: 1, preflight_generation: 1, source_revision_id: 'source',
        source_hash: 'source-hash', status: 'ready', source_language: 'en', page_count: 1, block_count: 1, unresolved_blocks: 0,
        blocks: [{ id: 'block', kind: 'paragraph', source_text: 'Original paragraph.' }] },
    };
    return route.fulfill({ json: values[path] ?? { items: [] }, headers: { ETag: `"${preferences.generation}"` } });
  });
  return { writes, errors };
}

for (const width of [390, 1440]) test(`target language stays beside the selected model and follows its supported languages at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  const { writes, errors } = await fixture(page);
  await page.goto('/#/settings');
  const target = page.locator('#default-locale'), service = page.locator('#settings-service');
  await expect(service.locator('#default-locale')).toBeVisible();
  await expect(page.locator('#settings-reading #default-locale')).toHaveCount(0);
  await expect(target).toHaveValue('de');
  await expect(target.locator('option[value="de"]')).toBeDisabled();
  await expect(target).toHaveAttribute('aria-invalid', 'true');
  await expect(target.locator('option[value="fr"]')).toHaveCount(0);
  await expect(target.locator('option[value="__custom"]')).toHaveCount(0);
  const save = service.getByRole('button', { name: '保存默认翻译语言', exact: true });
  await expect(save).toBeDisabled();
  await target.selectOption('ja');
  await save.click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ path: '/settings/preferences', body: { locale: 'ja' } });
  await service.getByRole('region', { name: '本地翻译模型', exact: true }).getByLabel('具体模型 ID', { exact: true }).selectOption(secondModel);
  await expect(target).toHaveValue('ja');
  await expect(target.locator('option[value="ja"]')).toBeDisabled();
  await expect(target.locator('option[value="de"]')).toBeEnabled();
  await expect(target.locator('option[value="ar"]')).toBeEnabled();
  await expect(save).toBeDisabled();
  expect(writes).toHaveLength(1);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await target.scrollIntoViewIfNeeded();
  await page.screenshot({ path: outputDirectory(`model-target-language-${width}.png`) });
  expect(errors).toEqual([]);
});

test('new translation selectors use model support while source language remains unrestricted', async ({ page }) => {
  const { writes, errors } = await fixture(page, { locale: 'ja' });
  for (const [route, selector] of [['upload', '#upload-language'], ['preflight/import', '#target-locale'], ['documents/doc', '#new-locale']]) {
    await page.goto(`/#/${route}`);
    if (route.startsWith('documents')) await page.getByText('添加翻译语言', { exact: true }).click();
    const target = page.locator(selector);
    await expect(target.locator('option[value="ja"]')).toBeEnabled();
    await expect(target.locator('option[value="fr"]')).toHaveCount(0);
    await expect(target.locator('option[value="__custom"]')).toHaveCount(0);
    if (route.startsWith('preflight')) await expect(page.locator('#source-language option[value="fr"]')).toHaveCount(1);
  }
  expect(writes).toEqual([]); expect(errors).toEqual([]);
});

test('unsupported recent languages cannot escape restricted native or searchable targets', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('paper-translation:recent-languages:v1', JSON.stringify(['fr', 'pt-BR', 'sr-Latn-RS', 'ja'])));
  const { writes, errors } = await fixture(page, { locale: 'en' });
  await page.goto('/#/settings');
  const target = page.locator('#default-locale'), picker = page.locator('.translation-language-settings .language-picker');
  await target.focus();
  for (const locale of ['fr', 'pt-BR', 'sr-Latn-RS', '__custom']) await expect(target.locator(`option[value="${locale}"]`)).toHaveCount(0);
  await expect(target.locator('optgroup[label="最近使用"] option')).toHaveText(['日本語']);
  await picker.getByRole('button', { name: '查找语言', exact: true }).click();
  const panel = picker.getByRole('region'), search = panel.getByRole('combobox');
  await expect(panel.getByRole('option')).toHaveCount(4);
  for (const query of ['fr', 'pt-BR', 'sr-Latn-RS']) {
    await search.fill(query);
    await expect(panel.getByRole('option')).toHaveCount(0);
    await expect(panel.getByRole('status')).toHaveText('未找到匹配的语言。请更换搜索关键词。');
    await search.press('Enter');
    await expect(target).toHaveValue('en');
  }
  await expect(picker.locator('input[id="default-locale-code"]')).toHaveCount(0);
  await search.fill('ja');
  await search.press('Enter');
  await expect(target).toHaveValue('ja');
  expect(writes).toEqual([]); expect(errors).toEqual([]);
});

test('UI language changes preserve unsaved model and locale; locale saves use fresh CAS without provider writes', async ({ page }) => {
  const { writes, errors } = await fixture(page, { locale: 'en' });
  await page.goto('/#/settings');
  const target = page.locator('#default-locale'), model = page.locator('#settings-service .local-model-settings:has(#default-locale) .model-language-row > label select');
  await model.selectOption(secondModel);
  await target.selectOption('ar');
  for (const locale of ['en', 'zh-Hant', 'en']) {
    await page.locator('#ui-language').selectOption(locale);
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
    await expect(target).toHaveValue('ar');
    await expect(model).toHaveValue(secondModel);
    expect(writes).toEqual([]);
  }
  const save = page.locator('.translation-language-settings').getByRole('button', { name: 'Save default translation language', exact: true });
  await save.click();
  await expect.poll(() => writes.length).toBe(1);
  await target.selectOption('de');
  await save.click();
  await expect.poll(() => writes.length).toBe(2);
  expect(writes).toEqual([
    { path: '/settings/preferences', body: { locale: 'ar' } },
    { path: '/settings/preferences', body: { locale: 'de' } },
  ]);
  await expect(model).toHaveValue(secondModel);
  await expect(page.locator('.settings-draft-summary')).toBeVisible();
  expect(errors).toEqual([]);
});

test('a translation-language save conflict retains the choice and never resends automatically', async ({ page }) => {
  const { writes, errors } = await fixture(page, { locale: 'en' });
  let attempts = 0;
  await page.route('**/api/v1/settings/preferences', route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    attempts++;
    expect(route.request().headers()['if-match']).toBe('"1"');
    expect(route.request().postDataJSON()).toEqual({ locale: 'ja' });
    return route.fulfill({ status: 412, json: { error: { code: 'PRECONDITION_FAILED', message: 'Synthetic preference conflict' } } });
  });
  await page.goto('/#/settings');
  const target = page.locator('#default-locale'), section = page.locator('.translation-language-settings');
  await target.selectOption('ja');
  await section.getByRole('button', { name: '保存默认翻译语言', exact: true }).click();
  await expect(section.getByRole('alert')).toContainText('PRECONDITION_FAILED');
  await page.locator('#ui-language').selectOption('en');
  await expect(target).toHaveValue('ja');
  await expect(section.getByRole('button', { name: 'Save default translation language', exact: true })).toBeDisabled();
  expect(attempts).toBe(1);
  expect(writes).toEqual([]); expect(errors).toEqual([]);
});

test('Enter in a custom default locale saves only that locale and preserves an unsaved API model', async ({ page }) => {
  const { writes, errors } = await fixture(page, { local: false, locale: 'en', supported: null });
  await page.goto('/#/settings');
  const model = page.getByLabel('模型 ID', { exact: true });
  await model.fill('unsaved-custom-api-model');
  await page.locator('#default-locale').selectOption('__custom');
  const code = page.locator('#default-locale-code');
  await code.fill('sr-Latn-RS');
  await code.press('Enter');
  await expect.poll(() => writes.length).toBe(1);
  expect(writes).toEqual([{ path: '/settings/preferences', body: { locale: 'sr-Latn-RS' } }]);
  await expect(model).toHaveValue('unsaved-custom-api-model');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('a pending default-locale save prevents interface switching until its confirmed choice is retained', async ({ page }) => {
  const { writes, errors } = await fixture(page, { local: false, locale: 'en', supported: null });
  let release!: () => void;
  const released = new Promise<void>(resolve => { release = resolve; });
  let pending = false;
  await page.route('**/api/v1/settings/preferences', async route => {
    if (route.request().method() !== 'PATCH') return route.fallback();
    pending = true;
    await released;
    return route.fallback();
  });
  await page.goto('/#/settings');
  const target = page.locator('#default-locale'), protocol = page.getByLabel('接口类型', { exact: true });
  await target.selectOption('ja');
  await page.getByRole('button', { name: '保存默认翻译语言', exact: true }).click();
  await expect.poll(() => pending).toBe(true);
  await expect(target).toBeDisabled();
  await expect(protocol).toBeDisabled();
  await expect(page.getByLabel('模型 ID', { exact: true })).toBeDisabled();
  release();
  await expect(protocol).toBeEnabled();
  await expect(target).toHaveValue('ja');
  await protocol.selectOption('local_translation');
  await expect(page.locator('#default-locale')).toHaveValue('ja');
  await protocol.selectOption('responses');
  await expect(page.locator('#default-locale')).toHaveValue('ja');
  expect(writes).toEqual([{ path: '/settings/preferences', body: { locale: 'ja' } }]);
  expect(errors).toEqual([]);
});

test('custom API models without declared support retain all languages and custom canonical tags', async ({ page }) => {
  const { writes, errors } = await fixture(page, { local: false, locale: 'pt-BR', supported: null });
  await page.goto('/#/settings');
  const target = page.locator('#default-locale');
  await expect(target).toHaveValue('pt-BR');
  await expect(target.locator('option[value="fr"]')).toBeEnabled();
  await target.selectOption('__custom');
  await page.getByLabel('语言代码（如 fil、pt-BR）', { exact: true }).fill('sr-Latn-RS');
  await page.getByRole('button', { name: '保存默认翻译语言', exact: true }).click();
  await expect.poll(() => writes.length).toBe(1);
  expect(writes[0]).toEqual({ path: '/settings/preferences', body: { locale: 'sr-Latn-RS' } });
  expect(errors).toEqual([]);
});
