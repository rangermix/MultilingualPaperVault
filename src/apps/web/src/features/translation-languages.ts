import { isLanguageTag } from '../languages';

export type TargetLanguageMatch = 'exact' | 'language';

/** Match the model's declared locale contract without changing the saved tag. */
export function supportsTargetLanguage(value: string, supported?: readonly string[] | null, match: TargetLanguageMatch = 'language'): boolean {
  if (!isLanguageTag(value)) return false;
  if (supported == null) return true;
  try {
    const locale = new Intl.Locale(value);
    if (match === 'exact') return supported.some(tag => new Intl.Locale(tag).toString() === locale.toString());
    const family = locale.language === 'tl' ? 'fil' : locale.language;
    return supported.some(tag => {
      const candidate = new Intl.Locale(tag);
      const candidateFamily = candidate.language === 'tl' ? 'fil' : candidate.language;
      if (candidateFamily !== family) return false;
      // A script-specific Chinese declaration does not imply the other script.
      return family !== 'zh' || !candidate.script || candidate.script === locale.maximize().script;
    });
  } catch { return false; }
}
