/* app.js — bootstrap: wire all modules together, bind UI events */
(function () {
  'use strict';

  // ── Hold-to-record button ─────────────────────────────────────────────────
  const recordBtn   = document.getElementById('record-btn');
  const sendBtn     = document.getElementById('send-btn');
  const interruptBtn = document.getElementById('interrupt-btn');
  const textInput   = document.getElementById('text-input');
  const micSvg      = recordBtn.querySelector('.mic-svg');
  const stopSvg     = recordBtn.querySelector('.stop-svg');

  function _startRecording() {
    AudioCapture.start().catch(e => {
      console.error('Mic error:', e);
      alert('Microphone access denied or unavailable.');
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

  // ── Text send ────────────────────────────────────────────────────────────
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
    // Reuse a simple in-memory analyser-like object for the capture visualiser
    if (AudioCapture.isRecording()) {
      // The visualiser reads from _analyser — for capture we fake it via a ScriptProcessor-less path
      // Instead we drive the orb colour directly via setMode without a real AnalyserNode
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
    Conversations.setActiveId(msg.conversation_id);
    Conversations.load();
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
    // Begin assistant bubble immediately
    Transcript.beginAssistantMessage(msg.message_id || '_pending');
  });

  WS.on('llm_token', msg => {
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
      if (m.role === 'user')      Transcript.addUserMessage(m.content, null);
      else if (m.role === 'assistant') {
        Transcript.beginAssistantMessage(m.id || Math.random().toString());
        Transcript.finaliseAssistant(m.id || Math.random().toString(), m.content);
      }
    });
  });

  // text_input also needs an assistant bubble (server won't send transcript_final)
  WS.on('state_change', msg => {
    if (msg.state === 'llm_generating') {
      // Only create bubble if there isn't already a pending one
      // (transcript_final creates it for voice; text_input we handle on send)
    }
  });

  // When user sends text we create the bubble immediately
  const _origSendText = _sendText; // captured above
  // Override send to also open assistant bubble
  sendBtn.removeEventListener('click', _sendText);
  sendBtn.addEventListener('click', () => {
    const text = textInput.value.trim();
    if (!text) return;
    WS.send({ type: 'text_input', text });
    Transcript.addUserMessage(text, null);
    Transcript.beginAssistantMessage('text_' + Date.now());
    textInput.value = '';
    textInput.style.height = 'auto';
  });

  WS.on('error', msg => {
    console.error('Server error:', msg.code, msg.message);
  });

  // ── Boot ─────────────────────────────────────────────────────────────────
  WS.connect();
})();
