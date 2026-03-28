/* Orb visualiser — reacts to mic input (listening) or TTS output (speaking) */
const Visualizer = (() => {
  const canvas = document.getElementById('viz-canvas');
  const ctx = canvas.getContext('2d');
  let _analyser = null;
  let _data = null;
  let _mode = 'idle';    // idle | listening | speaking
  let _raf = null;

  // ── Resize canvas to match CSS display size ──────────────────────────────
  function resize() {
    const r = canvas.getBoundingClientRect();
    canvas.width  = r.width  * devicePixelRatio;
    canvas.height = r.height * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  // ── Set analyser + mode ──────────────────────────────────────────────────
  function setMode(mode, analyser) {
    _mode = mode;
    _analyser = analyser || null;
    _data = _analyser ? new Uint8Array(_analyser.frequencyBinCount) : null;
  }

  // ── Main draw loop ───────────────────────────────────────────────────────
  function _draw() {
    _raf = requestAnimationFrame(_draw);

    const W = canvas.width  / devicePixelRatio;
    const H = canvas.height / devicePixelRatio;
    const cx = W / 2, cy = H / 2;

    ctx.clearRect(0, 0, W, H);

    // Compute RMS amplitude
    let amp = 0;
    if (_analyser && _data) {
      _analyser.getByteTimeDomainData(_data);
      let sum = 0;
      for (let i = 0; i < _data.length; i++) {
        const v = (_data[i] - 128) / 128;
        sum += v * v;
      }
      amp = Math.sqrt(sum / _data.length);
    }

    const baseR = Math.min(cx, cy) * 0.38;
    const R = baseR + amp * baseR * 1.6;

    // Outer glow ring
    const glow = ctx.createRadialGradient(cx, cy, R * 0.5, cx, cy, R * 1.8);
    if (_mode === 'listening') {
      glow.addColorStop(0, `rgba(124,110,245,${0.18 + amp * 0.25})`);
      glow.addColorStop(1, 'rgba(124,110,245,0)');
    } else if (_mode === 'speaking') {
      glow.addColorStop(0, `rgba(180,100,255,${0.18 + amp * 0.25})`);
      glow.addColorStop(1, 'rgba(80,0,180,0)');
    } else {
      glow.addColorStop(0, 'rgba(80,80,120,0.10)');
      glow.addColorStop(1, 'rgba(40,40,60,0)');
    }
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.8, 0, Math.PI * 2);
    ctx.fillStyle = glow;
    ctx.fill();

    // Core orb
    const grad = ctx.createRadialGradient(cx - R * 0.25, cy - R * 0.25, 0, cx, cy, R);
    if (_mode === 'listening') {
      grad.addColorStop(0, `rgba(180,160,255,${0.95 + amp * 0.05})`);
      grad.addColorStop(0.5, `rgba(100,80,230,0.9)`);
      grad.addColorStop(1, 'rgba(40,20,120,0.8)');
    } else if (_mode === 'speaking') {
      grad.addColorStop(0, `rgba(220,160,255,${0.95 + amp * 0.05})`);
      grad.addColorStop(0.5, 'rgba(140,60,220,0.9)');
      grad.addColorStop(1, 'rgba(60,10,140,0.8)');
    } else {
      grad.addColorStop(0, 'rgba(120,120,160,0.6)');
      grad.addColorStop(1, 'rgba(40,40,70,0.5)');
    }
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();

    // Frequency bars (ring) when active
    if (_analyser && _data && amp > 0.01) {
      const freqData = new Uint8Array(_analyser.frequencyBinCount);
      _analyser.getByteFrequencyData(freqData);
      const bars = Math.min(48, freqData.length);
      const barMaxH = R * 0.55;
      ctx.save();
      ctx.translate(cx, cy);
      for (let i = 0; i < bars; i++) {
        const angle = (i / bars) * Math.PI * 2 - Math.PI / 2;
        const h = (freqData[i] / 255) * barMaxH;
        ctx.beginPath();
        ctx.moveTo(Math.cos(angle) * (R + 3), Math.sin(angle) * (R + 3));
        ctx.lineTo(Math.cos(angle) * (R + 3 + h), Math.sin(angle) * (R + 3 + h));
        ctx.strokeStyle = _mode === 'speaking'
          ? `rgba(200,120,255,${0.5 + (freqData[i] / 255) * 0.5})`
          : `rgba(140,110,255,${0.5 + (freqData[i] / 255) * 0.5})`;
        ctx.lineWidth = 2;
        ctx.lineCap = 'round';
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  _draw();

  return { setMode };
})();
