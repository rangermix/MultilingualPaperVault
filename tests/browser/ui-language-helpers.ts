import { expect, type Page } from '../../src/apps/web/node_modules/@playwright/test/index.mjs';

/** Exercise the real Settings control; other routes receive its browser storage event. */
export function uiLanguageSwitcher(page: Page, mock: (page: Page) => Promise<unknown>) {
  let settings: Page | undefined;
  return async (locale: string) => {
    if (page.url().endsWith('/#/settings')) {
      await page.locator('#ui-language').selectOption(locale);
    } else {
      if (!settings) {
        settings = await page.context().newPage();
        await mock(settings);
        await settings.goto('/#/settings');
      }
      await settings.locator('#ui-language').selectOption(locale);
    }
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
  };
}
