/* Profile modal — list, create, avatar upload, enrollment trigger */
const Profiles = (() => {
  const modal        = document.getElementById('profile-modal');
  const openBtn      = document.getElementById('profile-btn');
  const closeBtn     = document.getElementById('profile-modal-close');
  const listEl       = document.getElementById('profile-list');
  const addBtn       = document.getElementById('add-profile-btn');
  const addForm      = document.getElementById('add-profile-form');
  const nameInput    = document.getElementById('new-profile-name');
  const createBtn    = document.getElementById('create-profile-btn');
  const enrollOverlay = document.getElementById('enroll-overlay');
  const cancelEnroll = document.getElementById('cancel-enroll-btn');
  const enrollPrompt = document.getElementById('enroll-prompt');

  let _enrollProfileId = null;

  openBtn.addEventListener('click', () => { modal.hidden = false; _load(); });
  closeBtn.addEventListener('click', () => { modal.hidden = true; });
  modal.addEventListener('click', e => { if (e.target === modal) modal.hidden = true; });

  addBtn.addEventListener('click', () => {
    addForm.hidden = !addForm.hidden;
    if (!addForm.hidden) nameInput.focus();
  });

  createBtn.addEventListener('click', _createProfile);
  nameInput.addEventListener('keydown', e => { if (e.key === 'Enter') _createProfile(); });

  cancelEnroll.addEventListener('click', () => {
    WS.send({ type: 'cancel_enrollment' });
    enrollOverlay.hidden = true;
    _enrollProfileId = null;
  });

  async function _load() {
    const r = await fetch('/api/profiles/');
    const profiles = await r.json();
    _render(profiles);
  }

  function _render(profiles) {
    listEl.innerHTML = '';
    if (!profiles.length) {
      listEl.innerHTML = '<div style="color:var(--text3);font-size:13px;text-align:center;padding:12px">No profiles yet</div>';
      return;
    }
    profiles.forEach(p => {
      const el = document.createElement('div');
      el.className = 'profile-item';
      const avatarHtml = p.avatar_path
        ? `<img src="${p.avatar_path}" alt="${_esc(p.name)}">`
        : p.name.charAt(0).toUpperCase();
      el.innerHTML = `
        <div class="profile-avatar">${avatarHtml}</div>
        <div class="profile-info">
          <div class="profile-name">${_esc(p.name)}</div>
          <div class="profile-meta">${p.has_voice ? '🎤 Voice enrolled' : 'No voice'}</div>
        </div>
        <div class="profile-actions">
          <button class="icon-btn-sm" title="Upload avatar" data-action="avatar" data-id="${p.id}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </button>
          <button class="icon-btn-sm" title="Enroll voice" data-action="enroll" data-id="${p.id}" data-name="${_esc(p.name)}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
            </svg>
          </button>
          <button class="icon-btn-sm" title="Delete" data-action="delete" data-id="${p.id}" style="color:var(--text3)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14H6L5 6M10 11v6M14 11v6M9 6V4h6v2"/>
            </svg>
          </button>
        </div>`;

      el.querySelector('[data-action="avatar"]').addEventListener('click', () => _pickAvatar(p.id));
      el.querySelector('[data-action="enroll"]').addEventListener('click', () => _startEnrollment(p.id, p.name));
      el.querySelector('[data-action="delete"]').addEventListener('click', async () => {
        await fetch(`/api/profiles/${p.id}`, { method: 'DELETE' });
        _load();
      });

      listEl.appendChild(el);
    });
  }

  async function _createProfile() {
    const name = nameInput.value.trim();
    if (!name) return;
    await fetch('/api/profiles/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name })
    });
    nameInput.value = '';
    addForm.hidden = true;
    _load();
  }

  function _pickAvatar(profileId) {
    const inp = document.createElement('input');
    inp.type = 'file'; inp.accept = 'image/*';
    inp.onchange = async () => {
      if (!inp.files[0]) return;
      const fd = new FormData();
      fd.append('file', inp.files[0]);
      await fetch(`/api/profiles/${profileId}/avatar`, { method: 'POST', body: fd });
      _load();
    };
    inp.click();
  }

  function _startEnrollment(profileId, name) {
    _enrollProfileId = profileId;
    enrollPrompt.textContent = `Say a short phrase 3 times for "${name}"`;
    enrollOverlay.hidden = false;
    modal.hidden = true;
    _resetDots();
    WS.send({ type: 'start_enrollment', profile_id: profileId });
  }

  function _resetDots() {
    [1,2,3].forEach(i => {
      const d = document.getElementById(`edot-${i}`);
      if (d) d.className = 'enroll-dot';
    });
  }

  // Handle enrollment progress from server
  WS.on('enrollment_progress', msg => {
    const n = msg.samples_collected || 0;
    [1,2,3].forEach(i => {
      const d = document.getElementById(`edot-${i}`);
      if (!d) return;
      if (i < n)  d.className = 'enroll-dot done';
      else if (i === n) d.className = 'enroll-dot active';
      else d.className = 'enroll-dot';
    });
  });

  WS.on('enrollment_done', () => {
    [1,2,3].forEach(i => {
      const d = document.getElementById(`edot-${i}`);
      if (d) d.className = 'enroll-dot done';
    });
    setTimeout(() => {
      enrollOverlay.hidden = true;
      _enrollProfileId = null;
      _resetDots();
    }, 1000);
  });

  function _esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return {};
})();
