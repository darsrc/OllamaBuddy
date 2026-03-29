/* app.js — bootstrap: wire all modules together, bind UI events */
(function () {
  'use strict';

  // ── Hold-to-record button ─────────────────────────────────────────────────
  const recordBtn    = document.getElementById('record-btn');
  const sendBtn      = document.getElementById('send-btn');
  const interruptBtn = document.getElementById('interrupt-btn');
  const textInput    = document.getElementById('text-input');
  const micSvg       = recordBtn.querySelector('.mic-svg');
  const stopSvg      = recordBtn.querySelector('.stop-svg');

  function _startRecording() {
    AudioCapture.start().catch(e => {
      console.error('Mic error:', e);
      _showMicBanner();
    });
    recordBtn.classList.add('active');
    micSvg.style.display = 'none';
    stopSvg.style.display = '';
  }

  function _stopRecording() {
    AudioCapture.stop();
    recordBtn.classList.remove('active');
    micSvg.style.display = '';
    stopSvg.style.display = 'none';
  }

  // Mouse
  recordBtn.addEventListener('mousedown', e => { e.preventDefault(); _startRecording(); });
  document.addEventListener('mouseup',  () => { if (AudioCapture.isRecording()) _stopRecording(); });

  // Touch (mobile)
  recordBtn.addEventListener('touchstart', e => { e.preventDefault(); _startRecording(); }, { passive: false });
  recordBtn.addEventListener('touchend',   e => { e.preventDefault(); _stopRecording(); });
  recordBtn.addEventListener('touchcancel',() => { if (AudioCapture.isRecording()) _stopRecording(); });

  // ── Inline mic-denied banner ─────────────────────────────────────────────
  function _showMicBanner() {
    if (document.getElementById('mic-denied-banner')) return;
    const b = document.createElement('div');
    b.id = 'mic-denied-banner';
    b.className = 'inline-banner inline-banner--warn';
    b.innerHTML = `
      <span>🎤 Microphone access denied. Check your browser permissions and try again.</span>
      <button class="inline-banner-close" aria-label="Dismiss">✕</button>`;
    b.querySelector('.inline-banner-close').addEventListener('click', () => b.remove());
    document.getElementById('input-area').prepend(b);
    // Reset button appearance
    recordBtn.classList.remove('active');
    micSvg.style.display = '';
    stopSvg.style.display = 'none';
  }

  // ── Model not installed in Ollama banner ─────────────────────────────────
  function _showModelMissingBanner(model) {
    if (document.getElementById('model-missing-banner')) return;
    const b = document.createElement('div');
    b.id = 'model-missing-banner';
    b.className = 'inline-banner inline-banner--warn';
    b.innerHTML = `
      <span>⚠ Model <strong>${model}</strong> is not installed in Ollama.
        Run <code>ollama pull ${model}</code> or select an available model in settings.</span>
      <button class="inline-banner-close" aria-label="Dismiss">✕</button>`;
    b.querySelector('.inline-banner-close').addEventListener('click', () => b.remove());
    document.getElementById('center-panel').prepend(b);
  }

  // ── Model download required banner ────────────────────────────────────────
  function _showDownloadBanner(msg) {
    if (document.getElementById('dl-banner')) return;
    const missing = [];
    if (!msg.tts_available) missing.push('Kokoro TTS (~330 MB)');
    if (!msg.stt_available) missing.push('Whisper STT (~75 MB)');
    if (!missing.length) return;

    const b = document.createElement('div');
    b.id = 'dl-banner';
    b.className = 'inline-banner inline-banner--info';
    b.innerHTML = `
      <span>Models not loaded: <strong>${missing.join(', ')}</strong>.
        Set <code>AUTO_DOWNLOAD_MODELS=true</code> in <code>.env</code> and restart.</span>
      <button class="inline-banner-close" aria-label="Dismiss">✕</button>`;
    b.querySelector('.inline-banner-close').addEventListener('click', () => b.remove());
    document.getElementById('center-panel').prepend(b);
  }

  // ── Mic permission indicator ─────────────────────────────────────────────
  async function _checkMicPermission() {
    try {
      const perm = await navigator.permissions.query({ name: 'microphone' });
      _applyMicState(perm.state);
      perm.addEventListener('change', () => _applyMicState(perm.state));
    } catch (_) { /* permissions API not supported */ }
  }

  function _applyMicState(state) {
    const dot = document.getElementById('mic-perm-dot');
    if (!dot) return;
    dot.className = 'mic-perm-dot mic-perm-' + state;
    dot.title = state === 'granted' ? 'Mic: allowed'
              : state === 'denied'  ? 'Mic: blocked — check browser settings'
              : 'Mic: click to allow';
  }

  // ── Text send ────────────────────────────────────────────────────────────
  // C8: single handler — no pre-created bubble (bubble opens on first llm_token, C7)
  function _sendText() {
    const text = textInput.value.trim();
    if (!text) return;
    WS.send({ type: 'text_input', text });
    Transcript.addUserMessage(text, null);
    textInput.value = '';
    textInput.style.height = 'auto';
  }
  sendBtn.addEventListener('click', _sendText);
  textInput.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _sendText(); }
  });
  // Auto-expand textarea
  textInput.addEventListener('input', () => {
    textInput.style.height = 'auto';
    textInput.style.height = Math.min(textInput.scrollHeight, 160) + 'px';
  });

  // ── Interrupt ────────────────────────────────────────────────────────────
  interruptBtn.addEventListener('click', () => {
    WS.send({ type: 'interrupt' });
    AudioPlayback.interrupt();
    Visualizer.setMode('idle', null);
  });

  // ── New chat ─────────────────────────────────────────────────────────────
  document.getElementById('new-chat-btn').addEventListener('click', () => {
    WS.send({ type: 'new_conversation' });
    Transcript.clear();
    document.getElementById('sidebar-left').classList.remove('open');
  });

  // ── Mic amplitude → visualiser ───────────────────────────────────────────
  AudioCapture.setAmplitudeCallback(amp => {
    if (AudioCapture.isRecording()) {
      // visualiser driven by setMode('listening') — amplitude available for future use
    }
  });

  // ═══════════════════ WebSocket event handlers ═══════════════════════════

  WS.on('_connected', () => {
    console.info('WS connected');
  });

  WS.on('_disconnected', () => {
    Settings.setState('idle');
    const ollamaDot = document.getElementById('ollama-dot');
    const ollamaLabel = document.getElementById('ollama-label');
    ollamaDot.className = 'status-dot disconnected';
    ollamaLabel.textContent = 'Disconnected';
  });

  WS.on('session_ready', msg => {
    Settings.populate(msg);
    if (msg.conversation_id) Conversations.setActiveId(msg.conversation_id);
    Conversations.load();
    // Show download banner if models missing
    if (msg.tts_available === false || msg.stt_available === false) {
      _showDownloadBanner(msg);
    }
    // B2: warn if configured model isn't installed in Ollama
    const configuredModel = msg.settings?.model;
    const available = msg.available_models || [];
    if (configuredModel && available.length && !available.includes(configuredModel)) {
      _showModelMissingBanner(configuredModel);
    }
  });

  WS.on('state_change', msg => {
    const state = msg.state;
    Settings.setState(state);

    if (state === 'listening') {
      Visualizer.setMode('listening', null);
      Transcript.setLiveText('Listening…');
      WakeLock.acquire();
    } else if (state === 'tts_playing') {
      Visualizer.setMode('speaking', AudioPlayback.getAnalyser());
      Transcript.clearLive();
    } else if (state === 'idle' || state === 'interrupted') {
      Visualizer.setMode('idle', null);
      Transcript.clearLive();
      WakeLock.release();
    } else if (state === 'transcribing') {
      Transcript.setLiveText('Transcribing…');
    }
  });

  WS.on('transcript_partial', msg => {
    Transcript.setLiveText(msg.text);
  });

  WS.on('transcript_final', msg => {
    Transcript.clearLive();
    Transcript.addUserMessage(msg.text, msg.speaker_id);
    // Begin assistant bubble immediately for voice turns
    Transcript.beginAssistantMessage(msg.message_id || '_pending');
  });

  WS.on('llm_token', msg => {
    // C7: open bubble on first token if not already open (covers text_input path)
    if (!Transcript.hasPending(msg.message_id)) {
      Transcript.beginAssistantMessage(msg.message_id);
    }
    Transcript.appendToken(msg.token, msg.message_id);
  });

  WS.on('llm_done', msg => {
    Transcript.finaliseAssistant(msg.message_id, msg.full_text);
    Conversations.load();  // refresh list (title may have been set)
  });

  WS.on('tool_start', msg => {
    Transcript.showToolCall(msg.tool, msg.query);
  });

  WS.on('tool_result', () => {
    Transcript.resolveToolCall();
  });

  WS.on('_binary', arrayBuffer => {
    AudioPlayback.handleBinaryFrame(arrayBuffer);
  });

  WS.on('tts_done', () => {
    Visualizer.setMode('idle', null);
  });

  WS.on('interrupted', () => {
    AudioPlayback.interrupt();
    Visualizer.setMode('idle', null);
    Transcript.clearLive();
  });

  WS.on('monitor_status', msg => {
    Monitor.update(msg);
    Monitor.setModel(msg.active_model || document.getElementById('model-select').value);
  });

  WS.on('new_conversation', msg => {
    Conversations.load();
    Conversations.setActiveId(msg.conversation_id);
  });

  WS.on('conversation_loaded', msg => {
    Transcript.clear();
    // Rebuild transcript from history
    (msg.messages || []).forEach(m => {
      if (m.role === 'user')           Transcript.addUserMessage(m.content, null);
      else if (m.role === 'assistant') {
        Transcript.beginAssistantMessage(m.id || Math.random().toString());
        Transcript.finaliseAssistant(m.id || Math.random().toString(), m.content);
      }
    });
  });

  WS.on('error', msg => {
    console.error('Server error:', msg.code, msg.message);
    Transcript.clearLive();
    Settings.setState('idle');
    // Show error briefly in the live bar so user knows something went wrong
    const text = msg.message ? `⚠ ${msg.message}` : '⚠ An error occurred';
    Transcript.setLiveText(text);
    setTimeout(() => Transcript.clearLive(), 5000);
  });

  // ── Boot ─────────────────────────────────────────────────────────────────
  _checkMicPermission();
  WS.connect();
})();
