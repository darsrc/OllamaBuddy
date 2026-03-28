/* TTS audio playback — seamlessly stitches Float32 chunks from server */
const AudioPlayback = (() => {
  const TTS_SAMPLE_RATE = 24000;
  const HEADER_BYTES = 16;  // 4×uint32 LE: [type, sampleRate, chunkIdx, totalSamples]

  let _ctx = null;
  let _analyser = null;
  let _nextStart = 0;
  let _playing = false;
  let _onDone = null;

  function _ensureContext() {
    if (_ctx && _ctx.state !== 'closed') return;
    _ctx = new AudioContext({ sampleRate: TTS_SAMPLE_RATE });
    _analyser = _ctx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.connect(_ctx.destination);
    _nextStart = 0;
  }

  function handleBinaryFrame(arrayBuffer) {
    if (arrayBuffer.byteLength < HEADER_BYTES) return;

    const view = new DataView(arrayBuffer);
    const tag      = view.getUint32(0, true);
    const sr       = view.getUint32(4, true);
    // chunkIdx  = view.getUint32(8,  true);  // unused client-side
    const nSamples = view.getUint32(12, true);

    if (tag !== 0x01) return;   // not TTS_AUDIO_PCM_F32

    const pcmBytes = new Uint8Array(arrayBuffer, HEADER_BYTES);
    const f32 = new Float32Array(pcmBytes.buffer, pcmBytes.byteOffset, nSamples);

    _ensureContext();
    if (_ctx.state === 'suspended') _ctx.resume();

    const buf = _ctx.createBuffer(1, f32.length, sr || TTS_SAMPLE_RATE);
    buf.copyToChannel(f32, 0);

    const src = _ctx.createBufferSource();
    src.buffer = buf;
    src.connect(_analyser);

    const now = _ctx.currentTime;
    const start = Math.max(now, _nextStart);
    src.start(start);
    _nextStart = start + buf.duration;

    _playing = true;
    src.onended = () => {
      // Check if this is the last queued buffer
      if (Math.abs(_ctx.currentTime - _nextStart) < 0.05) {
        _playing = false;
        if (_onDone) _onDone();
      }
    };
  }

  function interrupt() {
    if (_ctx) {
      // Close and null — will be recreated on next turn
      _ctx.close().catch(() => {});
      _ctx = null;
      _analyser = null;
    }
    _nextStart = 0;
    _playing = false;
  }

  function reset() {
    _nextStart = _ctx ? Math.max(_ctx.currentTime, _nextStart) : 0;
    _playing = false;
  }

  function getAnalyser() { return _analyser; }
  function isPlaying()   { return _playing; }
  function setOnDone(cb) { _onDone = cb; }

  return { handleBinaryFrame, interrupt, reset, getAnalyser, isPlaying, setOnDone };
})();
