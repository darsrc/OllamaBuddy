/* Left sidebar — conversation history list */
const Conversations = (() => {
  const list = document.getElementById('conv-list');
  let _active = null;

  async function load() {
    try {
      const r = await fetch('/api/conversations/');
      const data = await r.json();
      _render(data);
    } catch (e) {
      console.warn('Could not load conversations', e);
    }
  }

  function _render(convs) {
    list.innerHTML = '';
    if (!convs.length) {
      list.innerHTML = '<div class="conv-list-empty">No conversations yet</div>';
      return;
    }
    convs.forEach(c => {
      const el = document.createElement('div');
      el.className = 'conv-item' + (c.id === _active ? ' active' : '');
      el.dataset.id = c.id;

      const d = new Date(c.updated_at || c.created_at);
      const dateStr = _fmtDate(d);

      el.innerHTML = `
        <div class="conv-item-title" title="${_esc(c.title)}">${_esc(c.title)}</div>
        <span class="conv-item-date">${dateStr}</span>
        <button class="conv-item-del" title="Delete" data-del="${c.id}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>`;

      el.addEventListener('click', (e) => {
        if (e.target.closest('[data-del]')) return;
        _setActive(c.id);
        WS.send({ type: 'load_conversation', conversation_id: c.id });
        // On mobile close sidebar
        document.getElementById('sidebar-left').classList.remove('open');
      });

      el.querySelector('[data-del]').addEventListener('click', async (e) => {
        e.stopPropagation();
        await fetch(`/api/conversations/${c.id}`, { method: 'DELETE' });
        load();
      });

      list.appendChild(el);
    });
  }

  function _setActive(id) {
    _active = id;
    list.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === id);
    });
  }

  function setActiveId(id) { _setActive(id); }

  function prependNew(conv) {
    _active = conv.conversation_id || conv.id;
    load(); // reload list to reflect new entry
  }

  function _fmtDate(d) {
    const now = new Date();
    const diff = now - d;
    if (diff < 60000)  return 'just now';
    if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
    if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { load, setActiveId, prependNew };
})();
