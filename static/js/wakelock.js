/* Wake Lock — keeps the screen on while a voice session is active */
const WakeLock = (() => {
  let _sentinel = null;

  async function acquire() {
    if (!('wakeLock' in navigator)) return;
    try {
      _sentinel = await navigator.wakeLock.request('screen');
      _sentinel.addEventListener('release', () => { _sentinel = null; });
    } catch (e) {
      // Not critical — silently ignore (e.g. battery saver mode)
    }
  }

  async function release() {
    if (_sentinel) {
      await _sentinel.release().catch(() => {});
      _sentinel = null;
    }
  }

  // Re-acquire on page visibility change (required by spec after tab switch)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && _sentinel === null) {
      acquire();
    }
  });

  return { acquire, release };
})();
