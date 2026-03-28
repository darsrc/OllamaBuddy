import re
from typing import Optional


class TTSChunker:
    """Buffer LLM tokens and emit text chunks at natural speech boundaries."""

    _PUNCT_RE = re.compile(r"(?<=[.!?])\s+|(?<=[,;:])\s+")
    _WORD_RE = re.compile(r"\S+\s+")

    def __init__(self, mode: str = "punctuation"):
        assert mode in ("word", "punctuation", "paragraph"), f"Unknown mode: {mode}"
        self.mode = mode
        self.buffer = ""

    def feed(self, token: str) -> list[str]:
        """Consume a token, return ready-to-synthesise text chunks."""
        self.buffer += token
        chunks: list[str] = []

        if self.mode == "word":
            while True:
                m = self._WORD_RE.match(self.buffer)
                if not m:
                    break
                chunks.append(self.buffer[: m.end()].rstrip())
                self.buffer = self.buffer[m.end() :]

        elif self.mode == "punctuation":
            while True:
                m = self._PUNCT_RE.search(self.buffer)
                if not m:
                    break
                chunk = self.buffer[: m.start() + 1].strip()
                if chunk:
                    chunks.append(chunk)
                self.buffer = self.buffer[m.end() :]

        elif self.mode == "paragraph":
            parts = self.buffer.split("\n\n", 1)
            while len(parts) == 2:
                if parts[0].strip():
                    chunks.append(parts[0].strip())
                self.buffer = parts[1]
                parts = self.buffer.split("\n\n", 1)

        return [c for c in chunks if c.strip()]

    def flush(self) -> Optional[str]:
        """Return any remaining buffered text (call at LLM stream end)."""
        remaining = self.buffer.strip()
        self.buffer = ""
        return remaining or None

    def reset(self):
        self.buffer = ""

    def set_mode(self, mode: str):
        assert mode in ("word", "punctuation", "paragraph")
        self.mode = mode
