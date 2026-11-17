import ja from './extended/ja.json' with { type: 'json' };
import cs from './extended/cs.json' with { type: 'json' };
import da from './extended/da.json' with { type: 'json' };
import de from './extended/de.json' with { type: 'json' };
import es from './extended/es.json' with { type: 'json' };
import fr from './extended/fr.json' with { type: 'json' };
import id from './extended/id.json' with { type: 'json' };
import it from './extended/it.json' with { type: 'json' };
import hu from './extended/hu.json' with { type: 'json' };
import nl from './extended/nl.json' with { type: 'json' };
import pl from './extended/pl.json' with { type: 'json' };
import pt from './extended/pt.json' with { type: 'json' };
import ro from './extended/ro.json' with { type: 'json' };
import tr from './extended/tr.json' with { type: 'json' };
import ru from './extended/ru.json' with { type: 'json' };
import uk from './extended/uk.json' with { type: 'json' };
import ar from './extended/ar.json' with { type: 'json' };

/** Keep language choices recognizable in their own language in every interface. */
export const uiLocales = [
  { value: 'zh-Hans', label: '简体中文' },
  { value: 'zh-Hant', label: '繁體中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' },
  { value: 'cs', label: 'Čeština' },
  { value: 'da', label: 'Dansk' },
  { value: 'de', label: 'Deutsch' },
  { value: 'es', label: 'Español' },
  { value: 'fr', label: 'Français' },
  { value: 'id', label: 'Bahasa Indonesia' },
  { value: 'it', label: 'Italiano' },
  { value: 'hu', label: 'Magyar' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'pl', label: 'Polski' },
  { value: 'pt', label: 'Português' },
  { value: 'ro', label: 'Română' },
  { value: 'tr', label: 'Türkçe' },
  { value: 'ru', label: 'Русский' },
  { value: 'uk', label: 'Українська' },
  { value: 'ar', label: 'العربية' },
] as const;
export type UiLocale = typeof uiLocales[number]['value'];
export type ExtendedUiLocale = Exclude<UiLocale, 'zh-Hans' | 'zh-Hant' | 'en'>;

/** The English catalogue message is the stable key for these translations. */
export const extendedMessages: Record<ExtendedUiLocale, Readonly<Record<string, string>>> = {
  ja, cs, da, de, es, fr, id, it, hu, nl, pl, pt, ro, tr, ru, uk, ar,
};
