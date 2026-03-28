/* Right sidebar settings + capability bar + state bar */
const Settings = (() => {
  let _ready = false;   // M6: guard against sending settings before session_ready

  // ── Right panel elements ─────────────────────────────────────────────────
  const modelSel    = document.getElementById('model-select');
  const tempRange   = document.getElementById('temperature');
  const tempVal     = document.getElementById('temp-val');
  const voiceSel    = document.getElementById('tts-voice');
  const modeSel     = document.getElementById('tts-mode');
  const speedRange  = document.getElementById('tts-speed');
  const speedVal    = document.getElementById('speed-val');
  const sysPrompt   = document.getElementById('system-prompt');
  const applyBtn    = document.getElementById('apply-btn');

  // ── State bar ─────────────────────────────────────────────────────────────
  const stateBar  = document.getElementById('state-bar');
  const stateText = document.getElementById('state-text');

  // ── Capability toggles ────────────────────────────────────────────────────
  const capSearch  = document.getElementById('cap-search');
  const capVoiceId = document.getElementById('cap-voiceid');

  // ── Top-bar toggles ───────────────────────────────────────────────────────
  document.getElementById('sidebar-toggle').addEventListener('click', () => {
    document.getElementById('sidebar-left').classList.toggle('open');
  });
  document.getElementById('right-panel-toggle').addEventListener('click', () => {
    document.getElementById('sidebar-right').classList.toggle('open');
  });
  document.getElementById('settings-btn').addEventListener('click', () => {
    document.getElementById('app-settings-modal').hidden = false;
  });
  document.getElementById('app-settings-close').addEventListener('click', () => {
    document.getElementById('app-settings-modal').hidden = true;
  });

  // ── Range live labels ─────────────────────────────────────────────────────
  tempRange.addEventListener('input', () => { tempVal.textContent = (+tempRange.value).toFixed(2); });
  speedRange.addEventListener('input', () => { speedVal.textContent = (+speedRange.value).toFixed(1); });

  // ── Apply button ──────────────────────────────────────────────────────────
  applyBtn.addEventListener('click', sendSettings);

  // ── Capability toggles ────────────────────────────────────────────────────
  capSearch.addEventListener('click', () => {
    capSearch.classList.toggle('active');
    sendSettings();
  });
  capVoiceId.addEventListener('click', () => {
    capVoiceId.classList.toggle('active');
    sendSettings();
  });

  function sendSettings() {
    if (!_ready) return;
    WS.send({
      type: 'settings_update',
      model: modelSel.value,
      temperature: +tempRange.value,
      tts_voice: voiceSel.value,
      tts_mode: modeSel.value,
      tts_speed: +speedRange.value,
      system_prompt: sysPrompt.value,
      search_enabled: capSearch.classList.contains('active'),
      voice_id_enabled: capVoiceId.classList.contains('active'),
    });
  }

  // ── Populate from session_ready ───────────────────────────────────────────
  function populate(data) {
    // Models
    if (data.available_models?.length) {
      modelSel.innerHTML = data.available_models.map(m =>
        `<option value="${m}"${m === data.settings?.model ? ' selected' : ''}>${m}</option>`
      ).join('');
    }
    // Voices
    if (data.available_voices?.length) {
      voiceSel.innerHTML = data.available_voices.map(v =>
        `<option value="${v}"${v === data.settings?.tts_voice ? ' selected' : ''}>${v}</option>`
      ).join('');
    }
    const s = data.settings || {};
    if (s.temperature != null) { tempRange.value = s.temperature; tempVal.textContent = (+s.temperature).toFixed(2); }
    if (s.tts_mode)    modeSel.value = s.tts_mode;
    if (s.tts_speed != null) { speedRange.value = s.tts_speed; speedVal.textContent = (+s.tts_speed).toFixed(1); }
    if (s.system_prompt) sysPrompt.value = s.system_prompt;
    Monitor.setModel(s.model || '–');
    _ready = true;
  }

  // ── State bar update ──────────────────────────────────────────────────────
  const STATE_LABELS = {
    idle: 'Ready', listening: 'Listening…', transcribing: 'Transcribing…',
    llm_generating: 'Thinking…', tts_playing: 'Speaking…',
    interrupted: 'Interrupted', enrolling: 'Enrolling…',
  };

  function setState(state) {
    stateBar.className = 'state-bar ' + state;
    stateText.textContent = STATE_LABELS[state] || state;

    const interruptBtn = document.getElementById('interrupt-btn');
    const sendBtn = document.getElementById('send-btn');
    const isGenerating = ['llm_generating','tts_playing'].includes(state);
    interruptBtn.hidden = !isGenerating;
    sendBtn.hidden = isGenerating;
  }

  return { populate, setState, sendSettings };
})();
