import { setAddress, t } from '../../shared/i18n';
import { ADDRESS_MAX } from '../../shared/ipc';
import type { AppContext } from '../app-context';
import { errorText } from '../backend/client';
import { h } from './dom';

/**
 * Sends the address to the backend for screening (set_profile) and saves the value it
 * echoes (status.profile.address). On an error the previous address stays and the reason is
 * shown. Resolves to whether it was saved.
 */
export async function saveAddress(app: AppContext, value: string): Promise<boolean> {
  const address = value.trim();
  try {
    const status = await app.backend.request(
      { type: 'set_profile', id: app.backend.newId('profile'), profile: { address } },
      'status',
      undefined,
      15_000,
    );
    const saved = status.profile?.address ?? address;
    app.backend.address = saved;
    setAddress(saved);
    await app.patchSettings({ address: saved });
    app.director.ui.say(t(saved ? 'address.savedSay' : 'address.clearedSay'), 3000);
    return true;
  } catch (err) {
    app.toasts.show(t('address.failedTitle'), [errorText(err)], 'error');
    return false;
  }
}

/**
 * "What should she call you?": a text field, quick-pick chips for the language (plus the
 * default) and a save button. Used by the settings panel and the onboarding card.
 */
export function addressField(app: AppContext, labelSuffix = ''): HTMLElement {
  const input = h('input', {
    class: 'field',
    maxlength: ADDRESS_MAX,
    placeholder: t('address.placeholder'),
    value: app.settings().address,
  });
  const save = h('button', { class: 'btn small primary', type: 'button' }, t('address.save'));
  const commit = async (value: string): Promise<void> => {
    save.disabled = true;
    const ok = await saveAddress(app, value);
    // Saved: show what the backend kept; refused: back to the previous address.
    input.value = app.settings().address;
    if (!ok) input.focus();
    save.disabled = false;
  };
  save.addEventListener('click', () => void commit(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') void commit(input.value);
  });
  const chips = h(
    'div',
    { class: 'chips' },
    h(
      'button',
      { class: 'chip', type: 'button', onclick: () => void commit('') },
      t('address.default'),
    ),
    ...t('address.chips')
      .split('|')
      .filter(Boolean)
      .map((chip) =>
        h('button', { class: 'chip', type: 'button', onclick: () => void commit(chip) }, chip),
      ),
  );
  return h(
    'div',
    { class: 'address-field' },
    h('label', {}, `${t('address.label')}${labelSuffix ? ` ${labelSuffix}` : ''}`),
    h('div', { class: 'row' }, input, save),
    chips,
    h('p', { class: 'hint' }, t('address.hint')),
  );
}
