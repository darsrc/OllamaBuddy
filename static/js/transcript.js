/* Transcript — render streaming messages in the center panel */
const Transcript = (() => {
  const scroll = document.getElementById('transcript-scroll');
  const inner  = document.getElementById('transcript-inner');
  const welcome = document.getElementById('welcome-card');
  const liveBar = document.getElementById('live-bar');
  const liveText = document.getElementById('live-text');

  let _pendingBubble = null;   // currently streaming assistant bubble
  let _pendingId = null;
  let _autoScroll = true;
  let _toolRow = null;

  scroll.addEventListener('scroll', () => {
    const { scrollTop, scrollHeight, clientHeight } = scroll;
    _autoScroll = scrollHeight - scrollTop - clientHeight < 60;
  });

  function _scrollBottom() {
    if (_autoScroll) scroll.scrollTop = scroll.scrollHeight;
  }

  function _removeWelcome() {
    if (welcome) welcome.remove();
  }

  // ── Public ───────────────────────────────────────────────────────────────

  function addUserMessage(text, speakerId) {
    _removeWelcome();
    const div = document.createElement('div');
    div.className = 'msg msg-user';
    const meta = speakerId
      ? `<div class="msg-meta"><span class="msg-speaker-badge">${_esc(speakerId)}</span></div>`
      : '';
    div.innerHTML = `${meta}<div class="msg-bubble">${_esc(text)}</div>`;
    inner.appendChild(div);
    _scrollBottom();
  }

  function beginAssistantMessage(messageId) {
    _removeWelcome();
    _pendingId = messageId;
    const div = document.createElement('div');
    div.className = 'msg msg-assistant';
    div.dataset.msgId = messageId;
    div.innerHTML = `
      <div class="msg-meta"><span>AI</span></div>
      <div class="msg-bubble typing-cursor">
        <span class="thinking-dots"><span></span><span></span><span></span></span>
      </div>`;
    inner.appendChild(div);
    _pendingBubble = div.querySelector('.msg-bubble');
    _scrollBottom();
  }

  function appendToken(token, messageId) {
    if (!_pendingBubble || _pendingId !== messageId) return;
    // Remove thinking dots on first real token
    const dots = _pendingBubble.querySelector('.thinking-dots');
    if (dots) dots.remove();
    _pendingBubble.textContent += token;
    _scrollBottom();
  }

  function finaliseAssistant(messageId, fullText) {
    const el = inner.querySelector(`[data-msg-id="${messageId}"] .msg-bubble`);
    if (el) {
      el.classList.remove('typing-cursor');
      el.textContent = fullText;
    }
    _pendingBubble = null;
    _pendingId = null;
    _toolRow = null;
    _scrollBottom();
  }

  function showToolCall(tool, query) {
    if (!_pendingBubble) return;
    _toolRow = document.createElement('div');
    _toolRow.className = 'tool-indicator';
    _toolRow.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
      </svg>
      Searching: <em>${_esc(query)}</em>…`;
    _pendingBubble.parentElement.insertBefore(_toolRow, _pendingBubble);
    _scrollBottom();
  }

  function resolveToolCall() {
    if (_toolRow) {
      _toolRow.querySelector('em').textContent += ' ✓';
    }
  }

  function setLiveText(text) {
    if (!text) {
      liveBar.hidden = true;
      return;
    }
    liveBar.hidden = false;
    liveText.textContent = text || 'Listening…';
  }

  function clearLive() { setLiveText(''); }

  function clear() {
    inner.innerHTML = '';
    _pendingBubble = null;
    _pendingId = null;
  }

  function _esc(s) {
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function hasPending(id) { return _pendingId === id; }

  return {
    addUserMessage, beginAssistantMessage, appendToken,
    finaliseAssistant, showToolCall, resolveToolCall,
    setLiveText, clearLive, clear, hasPending
  };
})();
