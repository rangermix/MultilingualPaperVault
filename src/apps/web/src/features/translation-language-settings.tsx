import { api, etagFor } from '../api';
import { ActionFeedback, ErrorNotice } from '../components';
import { useAction } from '../hooks';
import { t } from '../i18n';
import type { Dispatch, SetStateAction } from 'react';
import type { Preferences } from '../types';
import { LanguageSelect } from './language-select';
import { useSettingsForm, useSettingsRefresh } from './settings-state';
import { supportsTargetLanguage, type TargetLanguageMatch } from './translation-languages';

export type TranslationLanguageSettingsProps = {
  preferences?: Preferences; onSaved: (value: Preferences) => void; reload: () => void;
};

/** A separate preference save shares CAS state with the other Settings sections. */
export function TranslationLanguageSettings({ preferences, onSaved, reload, supportedLanguages, targetLanguageMatch, disabled, choice, onChoiceChange, onPendingChange }: TranslationLanguageSettingsProps & {
  supportedLanguages?: readonly string[] | null; targetLanguageMatch?: TargetLanguageMatch; disabled?: boolean; choice?: string; onChoiceChange: Dispatch<SetStateAction<string | undefined>>;
  onPendingChange?: (pending: boolean) => void;
}) {
  const action = useAction();
  const locale = choice ?? preferences?.locale ?? 'zh-Hans';
  const dirty = Boolean(preferences && locale !== preferences.locale);
  const canSave = Boolean(preferences && etagFor(preferences) && supportsTargetLanguage(locale, supportedLanguages, targetLanguageMatch) && !disabled && !action.pending && !action.error);
  const session = useSettingsForm('translation-language', { label: '默认翻译语言', dirty, pending: action.pending, canSave, save,
    discard: () => { onChoiceChange(undefined); action.clear(); } });
  const refresh = useSettingsRefresh(dirty, () => { action.clear(); reload(); });
  async function save() {
    if (!canSave) return false;
    let saved = false;
    onPendingChange?.(true);
    try {
      await action.run(async () => {
        const current = session?.preferences() ?? preferences;
        const value = await api<Preferences>('/settings/preferences', { method: 'PATCH', etag: etagFor(current), body: { locale } });
        session?.remember(value); onSaved(value);
        onChoiceChange(current => current === locale ? undefined : current); saved = true;
      }, '偏好已保存。');
    } finally { onPendingChange?.(false); }
    return saved;
  }
  return <div className="translation-language-settings" onKeyDown={event => {
    // The custom locale input must never implicitly submit its enclosing Provider form.
    if (event.key === 'Enter' && !event.defaultPrevented && !event.nativeEvent.isComposing && event.target instanceof HTMLInputElement) {
      event.preventDefault(); void save();
    }
  }}>
    <div className="field"><label htmlFor="default-locale">{t("默认翻译语言")}</label>
      <LanguageSelect id="default-locale" value={locale} supportedLanguages={supportedLanguages} targetLanguageMatch={targetLanguageMatch} disabled={!preferences || disabled || action.pending}
        onChange={value => { onChoiceChange(value); if (!action.error) action.clear(); }}/>
    </div>
    {supportedLanguages == null && <p className="settings-hint">{t("此模型的支持语言未提供；请确认服务支持所选语言。")}</p>}
    {dirty && <p className="settings-unsaved small">{t("未保存")}</p>}
    <ActionFeedback notice={action.notice}/><ErrorNotice error={action.error} retry={refresh.request}/>
    <button className="btn" type="button" disabled={!canSave} onClick={() => void save()}>{t("保存默认翻译语言")}</button>
    {refresh.confirmation}
  </div>;
}
