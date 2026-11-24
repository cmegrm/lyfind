/* Device-local reading preferences. Native controls and dialogs support keyboard navigation. */
(() => {
  'use strict';
  const KEY = 'lyfind-accessibility';
  const defaults = { textSize: 'normal', contrast: 'standard', motion: 'system' };
  const deviceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const root = document.documentElement;
  function normalize(value) {
    return { textSize: value?.textSize === 'large' ? 'large' : 'normal',
      contrast: value?.contrast === 'high' ? 'high' : 'standard',
      motion: value?.motion === 'reduced' ? 'reduced' : 'system' };
  }
  let preferences;
  try { preferences = normalize(JSON.parse(localStorage.getItem(KEY))); }
  catch { preferences = { ...defaults }; }

  const dialog = document.createElement('dialog');
  dialog.id = 'accessibility';
  dialog.className = 'accessibility-panel';
  dialog.setAttribute('aria-labelledby', 'accessibility-title');
  dialog.setAttribute('aria-describedby', 'accessibility-intro');
  dialog.innerHTML = `<div class="modal-head"><div><h2 id="accessibility-title" tabindex="-1">Accessibility</h2><p id="accessibility-intro">Make LyFind comfortable to use. Changes apply right away and stay on this browser.</p></div><button type="button" class="btn secondary sm" data-accessibility-close>Done</button></div>
    <div class="modal-body accessibility-options">
      <fieldset><legend>Text size</legend><div class="accessibility-size"><label><input type="radio" name="textSize" value="normal">Normal</label><label><input type="radio" name="textSize" value="large">Larger</label></div><p class="meta">Browser zoom and pinch-to-zoom still work.</p></fieldset>
      <label class="accessibility-check"><input type="checkbox" name="contrast" aria-labelledby="accessibility-contrast-label" aria-describedby="accessibility-contrast-hint"><span><strong id="accessibility-contrast-label">Higher contrast</strong><small id="accessibility-contrast-hint">Stronger text, borders, and buttons in light or dark mode.</small></span></label>
      <label class="field"><span>Motion</span><select name="motion" aria-describedby="accessibility-motion-hint"><option value="system">Follow my device</option><option value="reduced">Reduce motion</option></select><small id="accessibility-motion-hint"></small></label>
      <p class="note">Use Tab to move, Enter or Space to choose, and Escape to close. Keyboard focus and form guidance are always available.</p>
      <p class="sr-only" data-accessibility-status role="status" aria-live="polite" aria-atomic="true"></p>
    </div><div class="modal-actions"><button type="button" class="btn secondary" data-accessibility-reset>Reset accessibility settings</button></div>`;
  document.body.append(dialog);

  function syncControls() {
    dialog.querySelectorAll('[name=textSize]').forEach(input => { input.checked = input.value === preferences.textSize; });
    dialog.querySelector('[name=contrast]').checked = preferences.contrast === 'high';
    dialog.querySelector('[name=motion]').value = preferences.motion;
    dialog.querySelector('#accessibility-motion-hint').textContent = deviceMotion.matches
      ? 'Your device requests reduced motion. LyFind respects this automatically.'
      : 'Follow your device, or turn off decorative movement here.';
  }
  function apply({ save = false, announce = false } = {}) {
    root.dataset.textSize = preferences.textSize;
    root.dataset.contrast = preferences.contrast;
    root.dataset.reducedMotion = String(preferences.motion === 'reduced' || deviceMotion.matches);
    if (save) {
      try { localStorage.setItem(KEY, JSON.stringify(preferences)); } catch { /* preferences still work this visit */ }
    }
    syncControls();
    if (announce) dialog.querySelector('[data-accessibility-status]').textContent =
      `${preferences.textSize === 'large' ? 'Larger' : 'Normal'} text. ${preferences.contrast === 'high' ? 'Higher' : 'Standard'} contrast. ${root.dataset.reducedMotion === 'true' ? 'Reduced motion is on.' : 'Motion follows your device.'}`;
  }
  dialog.addEventListener('change', event => {
    const input = event.target;
    if (input.name === 'textSize') preferences.textSize = input.value;
    if (input.name === 'contrast') preferences.contrast = input.checked ? 'high' : 'standard';
    if (input.name === 'motion') preferences.motion = input.value;
    preferences = normalize(preferences);
    apply({ save: true, announce: true });
  });
  dialog.addEventListener('keydown', event => {
    if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) return;
    const controls = [...dialog.querySelectorAll('button, input, select, a[href], [tabindex]')].filter(el =>
      !el.disabled && el.tabIndex >= 0 && el.getClientRects().length && !(el.type === 'radio' && !el.checked));
    const first = controls[0], last = controls[controls.length - 1];
    const active = document.activeElement;
    if (active.tabIndex < 0 || !dialog.contains(active) || (event.shiftKey ? active === first : active === last)) {
      event.preventDefault();
      (event.shiftKey ? last : first)?.focus();
    }
  });
  dialog.querySelector('[data-accessibility-close]').addEventListener('click', () => dialog.close());
  dialog.querySelector('[data-accessibility-reset]').addEventListener('click', () => {
    preferences = { ...defaults };
    apply({ save: true, announce: true });
  });
  deviceMotion.addEventListener('change', () => apply({ announce: dialog.open }));
  window.addEventListener('storage', event => {
    if (event.key !== KEY && event.key !== null) return;
    try { preferences = normalize(JSON.parse(event.newValue)); } catch { preferences = { ...defaults }; }
    apply({ announce: dialog.open });
  });
  window.LyFindAccessibility = {
    open() {
      if (dialog.open) return;
      syncControls();
      dialog.showModal();
      dialog.querySelector('#accessibility-title').focus();
    }
  };
  apply();
})();
