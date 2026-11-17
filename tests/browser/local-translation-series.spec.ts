import { test, expect } from '../../src/apps/web/node_modules/@playwright/test/index.mjs';
import { outputDirectory } from './paths';

// Synthetic catalog responses verify selection only; they never prepare weights or run inference.
const hyLanguages = 'zh-Hans en fr pt es ja tr ru ar ko th it de vi ms id tl hi zh-Hant pl cs nl km my fa gu ur te mr he bn ta uk bo kk mn ug yue'.split(' ');
const translateGemmaLanguages = 'en ar-EG ar-SA bg-BG bn-IN ca-ES cs-CZ da-DK de-DE el-GR es-MX et-EE fa-IR fi-FI fil-PH fr-CA fr-FR gu-IN he-IL hi-IN hr-HR hu-HU id-ID is-IS it-IT ja-JP kn-IN ko-KR lt-LT lv-LV ml-IN mr-IN nl-NL no-NO pa-IN pl-PL pt-BR pt-PT ro-RO ru-RU sk-SK sl-SI sr-RS sv-SE sw-KE sw-TZ ta-IN te-IN th-TH tr-TR uk-UA ur-PK vi-VN zh-Hans zh-Hant zu-ZA'.split(' ');
const plamoLanguages = 'ja en zh-Hans zh-Hant ko ar az be bg bn ca ceb de es et eu fa fr gu he hi hr hu hy id it jv ka kk km lt lv ml mr ms my ne nl pa pl ru si sk sl sr sw ta te th tl ur uz vi'.split(' ');
const gguf = { format: 'gguf', runtime: 'llama.cpp', quantization: 'Q4_K_M', bits: 4 };
const mlx = { format: 'mlx', runtime: 'mlx', quantization: 'Q4', bits: 4 };
const safetensors = { format: 'safetensors', runtime: 'vllm', quantization: 'BF16', bits: 16 };
const sizeLabel = (row: { parameter_size: string; bits: number }) => `${row.parameter_size} · ${row.bits === 16 ? 'BF16' : 'Q4'}`;
const formatLabels: Record<string, string> = { gguf: 'GGUF', mlx: 'MLX', safetensors: 'Safetensors' };

const variants = [
  { family: 'hy', family_label: 'Hy-MT2', sizes: ['1.8B'], languages: hyLanguages, formats: [gguf] },
  { family: 'translategemma', family_label: 'TranslateGemma', sizes: ['4B', '12B', '27B'], languages: translateGemmaLanguages, formats: [gguf, mlx] },
  { family: 'plamo3', family_label: 'PLaMo 3 Translate', sizes: ['0.8B', '2B', '8B', '31B'], languages: plamoLanguages, formats: [gguf, safetensors] },
];

for (const width of [1440, 390]) test(`translation series browsing preserves saved model and filters targets at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  const errors: string[] = [], writes: { path: string; method: string }[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()); });
  const rows = variants.flatMap(variant => variant.sizes.flatMap(parameter_size => variant.formats.map(flavor => ({
    id: `synthetic-${variant.family}-${parameter_size}-${flavor.format}`,
    model_id: `synthetic/${variant.family}-${parameter_size}-${flavor.format}@sha256:fixture`,
    label: `${variant.family_label} ${parameter_size} ${flavor.quantization}`,
    family: variant.family, family_label: variant.family_label, parameter_size,
    ...flavor,
    repo: `synthetic/${variant.family}-${parameter_size}-${flavor.format}`, revision: 'a'.repeat(40),
    download_bytes: 1000000000, supported_target_languages: variant.languages,
    target_language_match: variant.family === 'hy' ? 'family' : 'exact',
    inference_backends: [flavor.runtime], default_backend: flavor.runtime, status: 'not_downloaded',
  }))));
  const saved = rows[0];
  const profile = { generation: 7, configured: true, dispatch_configuration_ready: true, config_source: 'managed',
    has_api_key: false, provider: 'local', api_protocol: 'local_translation', auth_mode: 'none',
    endpoint: 'http://local-translator:8090/v1/completions', model_id: saved.model_id, local_backend: 'llama.cpp',
    profile_hash: 'b'.repeat(64), cost_control_enabled: false, supported_target_languages: hyLanguages,
    max_input_tokens: 32768, max_output_tokens: 8192, max_unit_characters: 2000 };
  await page.route('**/api/v1/**', route => {
    const request = route.request(), path = new URL(request.url()).pathname.slice(7);
    if (request.method() !== 'GET') writes.push({ path, method: request.method() });
    const values: Record<string, unknown> = {
      '/settings/provider': profile, '/settings/local-models': { models: rows },
      '/settings/preferences': { generation: 3, locale: 'cs-CZ', theme: 'light' },
      '/settings/dispatch': { generation: 1, dispatch_disabled: false },
      '/settings/resources': { waiting_jobs: [], model_references: [] },
      '/capabilities': { source_mime_types: ['application/pdf'] }, '/jobs': { items: [] },
    };
    return route.fulfill({ json: values[path] ?? {}, headers: { ETag: '"7"' } });
  });
  await page.goto('/#/settings');
  await expect(page).toHaveURL(/#\/settings$/);
  await expect(page).toHaveTitle(/.+/);
  await expect(page.getByRole('heading', { name: 'AI 服务', exact: true })).toBeVisible();
  const region = page.getByRole('region', { name: '本地翻译模型', exact: true });
  const family = region.getByRole('combobox', { name: '模型系列', exact: true });
  const size = region.getByRole('combobox', { name: '参数规模与量化', exact: true });
  const format = region.getByRole('combobox', { name: '模型格式', exact: true });
  const model = region.getByRole('combobox', { name: '具体模型 ID', exact: true });
  const backend = region.getByRole('combobox', { name: '推理后端', exact: true });
  const target = region.locator('#default-locale');
  const save = page.getByRole('button', { name: '保存 AI 服务配置', exact: true });
  const prepare = region.getByRole('button', { name: '立即准备模型', exact: true });
  await expect(family.locator('option')).toHaveText(['请选择模型系列', 'Hy-MT2', 'TranslateGemma', 'PLaMo 3 Translate']);
  await expect(model).toHaveValue(saved.model_id);
  await expect(backend).toHaveValue('llama.cpp');
  await expect(target).toHaveValue('cs-CZ');

  for (const variant of variants.slice(1)) {
    await family.selectOption(variant.family);
    await expect(size.locator('option')).toHaveText(['请选择参数规模与量化', ...new Set(rows.filter(row => row.family === variant.family).map(sizeLabel))]);
    for (const parameterSize of variant.sizes) {
      for (const flavor of variant.formats) {
        const row = rows.find(value => value.family === variant.family && value.parameter_size === parameterSize && value.format === flavor.format)!;
        if (await size.inputValue() !== sizeLabel(row)) await size.selectOption(sizeLabel(row));
        const formats = rows.filter(value => value.family === variant.family && sizeLabel(value) === sizeLabel(row)).map(value => formatLabels[value.format]);
        await expect(format.locator('option')).toHaveText(['请选择格式', ...formats]);
        if (await format.inputValue() !== flavor.format) await format.selectOption(flavor.format);
        await expect(model.locator('option')).toHaveCount(2);
        await model.selectOption(row.model_id);
        await expect(model).toHaveValue(row.model_id);
        await expect(backend).toHaveValue(flavor.runtime);
        await expect(region.locator('.model-choice-name')).toHaveText(row.label);
        await expect(target).toHaveValue('cs-CZ');
        await expect(target.locator('option[value="zh-Hans"]')).toBeEnabled();
        await expect(target.locator('option[value="zh-Hant"]')).toBeEnabled();
        await expect(target.locator(`option[value="${variant.family === 'translategemma' ? 'ja-JP' : 'ja'}"]`)).toBeEnabled();
        await expect(target.locator(`option[value="${variant.family === 'translategemma' ? 'ja' : 'ja-JP'}"]`)).toHaveCount(0);
        await expect(target.locator('option[value="__custom"]')).toHaveCount(0);
        await expect(save).toBeEnabled();
        await expect(prepare).toBeEnabled();
      }
    }
    const last = rows.find(row => row.family === variant.family && row.parameter_size === variant.sizes.at(-1) && row.format === variant.formats.at(-1)!.format)!;
    await region.getByText('模型 ID 与性能说明', { exact: true }).click();
    await expect(region.locator('.model-choice-details')).toContainText(last.model_id);
    if (variant.family === 'translategemma') {
      await expect(target.locator('option[value="cs-CZ"]')).toBeEnabled();
      await expect(target.locator('option[value="cs"]')).toHaveCount(0);
      await expect(target.locator('option[value="pt-BR"]')).toBeEnabled();
      await expect(target.locator('option[value="pt-PT"]')).toBeEnabled();
      await expect(target.locator('option[value="pt"]')).toHaveCount(0);
      await expect(target.locator('option[value="az"]')).toHaveCount(0);
    } else {
      await expect(target.locator('option[value="cs-CZ"]')).toBeDisabled();
      await expect(target).toHaveAttribute('aria-invalid', 'true');
      await expect(target.locator('option[value="pt"]')).toHaveCount(0);
      await expect(target.locator('option[value="az"]')).toBeEnabled();
      await expect(target.locator('option[value="en-AU"]')).toHaveCount(0);
      await expect(region).not.toContainText('所选后端与当前模型或部署不兼容');
    }
    await region.getByText('模型 ID 与性能说明', { exact: true }).click();
    await region.screenshot({ path: outputDirectory(`translation-series-${variant.family}-${width}.png`) });
  }
  await family.selectOption('translategemma');
  await expect(model).toHaveValue(rows.find(row => row.family === 'translategemma' && row.parameter_size === '27B' && row.format === 'mlx')!.model_id);
  await size.selectOption('4B · Q4');
  await expect(model).toHaveValue(rows.find(row => row.family === 'translategemma' && row.parameter_size === '4B' && row.format === 'mlx')!.model_id);
  await format.selectOption('gguf');
  await expect(model).toHaveValue(rows.find(row => row.family === 'translategemma' && row.parameter_size === '4B' && row.format === 'gguf')!.model_id);
  await family.selectOption('hy');
  await expect(model).toHaveValue(saved.model_id);
  await expect(backend).toHaveValue('llama.cpp');
  await expect(target.locator('option[value="cs-CZ"]')).toBeEnabled();
  await family.selectOption('plamo3');
  await page.reload();
  await expect(family).toHaveValue('hy');
  await expect(model).toHaveValue(saved.model_id);
  await expect(backend).toHaveValue('llama.cpp');
  await expect(target).toHaveValue('cs-CZ');
  await expect(page.locator('vite-error-overlay')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  expect(writes).toEqual([]);
  expect(errors).toEqual([]);
});
