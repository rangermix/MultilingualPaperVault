import { coreMessages } from './locales/core';
import { extendedMessages, uiLocales } from './locales/extended';

const title = '对照文库 · 个人 PDF 知识库';
const noScript = '管理界面需要 JavaScript。已发布的静态阅读页面不需要 JavaScript 即可阅读完整正文。';
const escapeHtml = (value: string) => value.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);

/** Build-time fallback: without JavaScript there is no browser-language negotiation. */
export function localizeBootstrap(html: string): string {
  const alternatives = uiLocales.map(({ value: locale }) => {
    const text = locale === 'zh-Hans' ? noScript : locale === 'zh-Hant' ? coreMessages[noScript][1]
      : locale === 'en' ? coreMessages[noScript][0] : extendedMessages[locale][coreMessages[noScript][0]];
    return `<p lang="${locale}" dir="${locale === 'ar' ? 'rtl' : 'ltr'}">${escapeHtml(text)}</p>`;
  });
  return html.replace('<!--app-title-->', escapeHtml(coreMessages[title][0]))
    .replace('<!--app-noscript-->', alternatives.join(''));
}
