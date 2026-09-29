import { getLang, isLang, LANG_NAMES, LANGS, t } from '../../shared/i18n';
import type { AppContext } from '../app-context';
import { h } from './dom';

/**
 * Language picker (each language in its own name). Picking one patches the settings; the
 * switch itself (UI, tray, backend) happens when main.ts receives the new settings.
 */
export function languageField(app: AppContext, hint = false): HTMLElement {
  const select = h(
    'select',
    { class: 'field', 'aria-label': 'Language' },
    ...LANGS.map((lang) =>
      h('option', { value: lang, selected: lang === getLang(), lang }, LANG_NAMES[lang]),
    ),
  );
  select.addEventListener('change', () => {
    if (isLang(select.value)) void app.patchSettings({ lang: select.value });
  });
  return h(
    'label',
    { class: 'language-field' },
    t('lang.label'),
    select,
    hint ? h('small', { class: 'hint' }, t('lang.hint')) : null,
  );
}
