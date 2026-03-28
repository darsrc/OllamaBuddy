/* WebSocket connection — auto-reconnect, message router */
const WS = (() => {
  const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000];
  let _ws = null;
  let _retryIdx = 0;
  let _intentionalClose = false;
  const _handlers = {};   // type → [fn, ...]

  function connect() {
    _intentionalClose = false;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    _ws = new WebSocket(`${proto}://${location.host}/ws`);
    _ws.binaryType = 'arraybuffer';

    _ws.onopen = () => {
      _retryIdx = 0;
      _dispatch('_connected', {});
    };

    _ws.onclose = () => {
      _ws = null;
      _dispatch('_disconnected', {});
      if (!_intentionalClose) {
        const delay = RECONNECT_DELAYS[Math.min(_retryIdx++, RECONNECT_DELAYS.length - 1)];
        setTimeout(connect, delay);
      }
    };

    _ws.onerror = () => {/* close fires after error */};

    _ws.onmessage = (evt) => {
      if (evt.data instanceof ArrayBuffer) {
        _dispatch('_binary', evt.data);
      } else {
        try {
          const msg = JSON.parse(evt.data);
          _dispatch(msg.type, msg);
          _dispatch('*', msg);
        } catch (_) {}
      }
    };
  }

  function send(obj) {
    if (_ws?.readyState === WebSocket.OPEN) {
      _ws.send(JSON.stringify(obj));
    }
  }

  function sendBinary(buffer) {
    if (_ws?.readyState === WebSocket.OPEN) {
      _ws.send(buffer);
    }
  }

  function on(type, fn) {
    (_handlers[type] = _handlers[type] || []).push(fn);
  }

  function off(type, fn) {
    if (!_handlers[type]) return;
    _handlers[type] = _handlers[type].filter(f => f !== fn);
  }

  function _dispatch(type, data) {
    (_handlers[type] || []).forEach(fn => { try { fn(data); } catch (e) { console.error(e); } });
  }

  function close() { _intentionalClose = true; _ws?.close(); }
  function ready()  { return _ws?.readyState === WebSocket.OPEN; }

  return { connect, send, sendBinary, on, off, close, ready };
})();
