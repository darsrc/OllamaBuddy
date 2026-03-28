/* Audio capture — getUserMedia + AudioWorklet → binary WS frames */
const AudioCapture = (() => {
  const SAMPLE_RATE = 16000;
  const CHUNK_TAG_ONGOING = new Uint8Array([0x10, 0x00, 0x00, 0x00]);  // AUDIO_CHUNK
  const CHUNK_TAG_FINAL   = new Uint8Array([0x11, 0x00, 0x00, 0x00]);  // AUDIO_FINAL

  let _ctx = null;
  let _workletNode = null;
  let _sourceNode  = null;
  let _stream      = null;
  let _recording   = false;
  let _onAmplitude = null;   // callback(rms: 0–1) for visualiser

  // ── Inline AudioWorkletProcessor as a Blob URL ──────────────────────────
  const _processorSrc = `
class CaptureProcessor extends AudioWorkletProcessor {
  constructor() { super(); this._buf = []; }
  process(inputs) {
    const ch = inputs[0]?.[0];
    if (!ch) return true;
    // Downsample from context rate to 16kHz if needed (handled by AudioContext sampleRate)
    this.port.postMessage(ch.slice(), [ch.buffer]);
    return true;
  }
}
registerProcessor('capture-processor', CaptureProcessor);
`;
  const _processorURL = URL.createObjectURL(
    new Blob([_processorSrc], { type: 'application/javascript' })
  );

  async function _ensureContext() {
    if (_ctx && _ctx.state !== 'closed') return;
    _ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
    await _ctx.audioWorklet.addModule(_processorURL);
  }

  async function start() {
    if (_recording) return;
    await _ensureContext();

    _stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });

    _sourceNode = _ctx.createMediaStreamSource(_stream);

    _workletNode = new AudioWorkletNode(_ctx, 'capture-processor');
    _workletNode.port.onmessage = (e) => {
      const f32 = e.data;  // Float32Array

      // Amplitude callback for visualiser
      if (_onAmplitude) {
        let sum = 0;
        for (let i = 0; i < f32.length; i++) sum += f32[i] * f32[i];
        _onAmplitude(Math.sqrt(sum / f32.length));
      }

      if (!_recording) return;
      const tag = CHUNK_TAG_ONGOING;
      const body = new Uint8Array(f32.buffer);
      const frame = new Uint8Array(tag.length + body.length);
      frame.set(tag, 0);
      frame.set(body, tag.length);
      WS.sendBinary(frame.buffer);
    };

    _sourceNode.connect(_workletNode);
    _workletNode.connect(_ctx.destination);   // needed to keep worklet alive in some browsers

    _recording = true;
    WS.send({ type: 'recording_start' });
    WakeLock.acquire();
  }

  function stop() {
    if (!_recording) return;
    _recording = false;

    // Send a zero-sample AUDIO_FINAL to signal end
    const frame = new Uint8Array(CHUNK_TAG_FINAL.length);
    frame.set(CHUNK_TAG_FINAL, 0);
    WS.sendBinary(frame.buffer);

    WS.send({ type: 'recording_stop' });

    // Disconnect worklet but keep context alive for next recording
    try { _sourceNode?.disconnect(); } catch (_) {}
    try { _workletNode?.disconnect(); } catch (_) {}
    _stream?.getTracks().forEach(t => t.stop());
    _stream = null;
  }

  function setAmplitudeCallback(cb) { _onAmplitude = cb; }
  function isRecording() { return _recording; }

  return { start, stop, setAmplitudeCallback, isRecording };
})();
