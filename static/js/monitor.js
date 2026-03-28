/* Top-bar monitor — Ollama status badge + CPU/RAM sparklines */
const Monitor = (() => {
  const ollamaDot   = document.getElementById('ollama-dot');
  const ollamaLabel = document.getElementById('ollama-label');
  const modelName   = document.getElementById('active-model-name');
  const cpuVal      = document.getElementById('cpu-val');
  const ramVal      = document.getElementById('ram-val');
  const cpuSpark    = document.getElementById('cpu-spark');
  const ramSpark    = document.getElementById('ram-spark');

  function _drawSparkline(canvas, data, color) {
    const W = canvas.width, H = canvas.height;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);
    if (!data.length) return;

    const max = 100;
    const step = W / (data.length - 1 || 1);

    ctx.beginPath();
    data.forEach((v, i) => {
      const x = i * step;
      const y = H - (v / max) * (H - 2) - 1;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = 'round';
    ctx.stroke();

    // Fill under line
    ctx.lineTo(W, H); ctx.lineTo(0, H); ctx.closePath();
    const _inner = color.slice(color.indexOf('(') + 1, color.lastIndexOf(')'));
    ctx.fillStyle = `rgba(${_inner},0.12)`;
    ctx.fill();
  }

  function update(msg) {
    // Ollama status
    const s = msg.ollama_status || 'disconnected';
    ollamaDot.className = 'status-dot ' + s;
    ollamaLabel.textContent = s === 'connected' ? 'Ollama' : s;

    // Resource values
    cpuVal.textContent = msg.cpu_percent?.toFixed(0) + '%';
    ramVal.textContent = msg.ram_percent?.toFixed(0) + '%';

    // Sparklines
    _drawSparkline(cpuSpark, msg.cpu_history || [], 'rgb(124,110,245)');
    _drawSparkline(ramSpark,  msg.ram_history || [], 'rgb(76,175,125)');
  }

  function setModel(name) {
    modelName.textContent = name || '–';
  }

  return { update, setModel };
})();
