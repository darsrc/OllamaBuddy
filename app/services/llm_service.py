import asyncio
import logging
import uuid
from typing import Optional

from fastapi import WebSocket

from app.session.state import ConversationSession, SessionState
from app.session.tts_chunker import TTSChunker
from config import settings

logger = logging.getLogger(__name__)

_SEARXNG_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current or factual information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


class LLMService:
    async def run_turn(
        self,
        session: ConversationSession,
        ws: WebSocket,
        user_text: str,
        speaker_id: Optional[str] = None,
    ):
        """One full conversation turn: user text → LLM stream → TTS queue."""
        import ollama as _ollama
        from app.services.search_service import search_service
        from app.services.tts_service import tts_service

        session.state = SessionState.LLM_GENERATING
        message_id = str(uuid.uuid4())
        session.current_message_id = message_id

        # Add user turn to in-memory history
        session.messages.append({"role": "user", "content": user_text})

        # Build message list for Ollama
        history: list[dict] = []
        if session.settings.system_prompt:
            history.append({"role": "system", "content": session.settings.system_prompt})
        history.extend(session.messages[:-1])   # all but the last (user) message
        history.append({"role": "user", "content": user_text})

        tools = [_SEARXNG_TOOL] if session.settings.search_enabled else []
        client = _ollama.AsyncClient(host=settings.ollama_host)

        # ── Pass 1: tool-call detection (non-streaming) ───────────────────
        if tools:
            try:
                resp = await client.chat(
                    model=session.settings.model,
                    messages=history,
                    tools=tools,
                    options={
                        "temperature": session.settings.temperature,
                        "top_p": session.settings.top_p,
                    },
                )
                if resp.message.tool_calls:
                    for tc in resp.message.tool_calls:
                        if tc.function.name == "web_search":
                            query = tc.function.arguments.get("query", user_text)
                            n = tc.function.arguments.get("num_results", 5)
                            await ws.send_json(
                                {"type": "tool_start", "tool": "web_search", "query": query}
                            )
                            result = await search_service.search(query, n)
                            await ws.send_json(
                                {
                                    "type": "tool_result",
                                    "tool": "web_search",
                                    "summary": f"Results for: {query}",
                                }
                            )
                            # Append assistant + tool messages
                            tc_payload = {
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            }
                            history.append(
                                {
                                    "role": "assistant",
                                    "content": resp.message.content or "",
                                    "tool_calls": [tc_payload],
                                }
                            )
                            history.append(
                                {"role": "tool", "content": result, "name": "web_search"}
                            )
            except Exception as e:
                logger.warning(f"Tool call pass failed, falling back: {e}")
                # Prompt-injection fallback
                try:
                    result = await search_service.search(user_text)
                    history[-1]["content"] = (
                        f"{user_text}\n\n[WEB SEARCH CONTEXT]\n{result}"
                    )
                except Exception:
                    pass

        # Reset chunker
        if session.tts_chunker is None:
            session.tts_chunker = TTSChunker(mode=session.settings.tts_mode)
        else:
            session.tts_chunker.reset()
            session.tts_chunker.set_mode(session.settings.tts_mode)

        # Start TTS consumer as a sibling task
        session.tts_task = asyncio.create_task(
            self._tts_consumer(session, ws, message_id, tts_service)
        )

        # ── Pass 2: streaming response ────────────────────────────────────
        full_tokens: list[str] = []
        try:
            stream = await client.chat(
                model=session.settings.model,
                messages=history,
                stream=True,
                options={
                    "temperature": session.settings.temperature,
                    "top_p": session.settings.top_p,
                    "num_ctx": session.settings.num_ctx,
                },
            )
            async for chunk in stream:
                if session.interrupt_event.is_set():
                    try:
                        await stream.aclose()
                    except Exception:
                        pass
                    break

                token = chunk.message.content or ""
                if token:
                    full_tokens.append(token)
                    await ws.send_json(
                        {"type": "llm_token", "token": token, "message_id": message_id}
                    )
                    for text_chunk in session.tts_chunker.feed(token):
                        if not session.interrupt_event.is_set():
                            await session.tts_queue.put(text_chunk)

                await asyncio.sleep(0)  # yield — lets interrupt handler run

        except asyncio.CancelledError:
            logger.info("LLM stream cancelled")
        except Exception as e:
            logger.error(f"LLM stream error: {e}")
            await ws.send_json(
                {"type": "error", "code": "LLM_ERROR", "message": str(e)}
            )
        finally:
            # C4: sentinel always fires — prevents _tts_consumer deadlock on error/cancel
            if not session.interrupt_event.is_set():
                tail = session.tts_chunker.flush()
                if tail:
                    await session.tts_queue.put(tail)
            await session.tts_queue.put(None)

        full_text = "".join(full_tokens)
        # H3: update history; roll back user message if no response produced
        if full_text:
            session.messages.append({"role": "assistant", "content": full_text})
        elif session.messages and session.messages[-1]["role"] == "user":
            session.messages.pop()

        await ws.send_json(
            {"type": "llm_done", "message_id": message_id, "full_text": full_text}
        )

        # Wait for TTS consumer to finish
        if session.tts_task and not session.tts_task.done():
            try:
                await session.tts_task
            except asyncio.CancelledError:
                pass

    async def _tts_consumer(
        self,
        session: ConversationSession,
        ws: WebSocket,
        message_id: str,
        tts_service,
    ):
        session.state = SessionState.TTS_PLAYING
        chunk_index = 0
        try:
            while True:
                text = await session.tts_queue.get()
                if text is None:    # sentinel
                    break
                if session.interrupt_event.is_set():
                    # Drain queue
                    while not session.tts_queue.empty():
                        try:
                            session.tts_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    break

                try:
                    audio = await tts_service.synthesize(
                        text, session.settings.tts_voice, session.settings.tts_speed
                    )
                    if audio is not None and len(audio):
                        await ws.send_json(
                            {"type": "tts_chunk_start", "chunk_index": chunk_index}
                        )
                        await ws.send_bytes(
                            tts_service.make_audio_frame(audio, chunk_index)
                        )
                        await ws.send_json(
                            {"type": "tts_chunk_end", "chunk_index": chunk_index}
                        )
                        chunk_index += 1
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"TTS consumer error: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await ws.send_json({"type": "tts_done", "message_id": message_id})
            if not session.interrupt_event.is_set():
                session.state = SessionState.IDLE


llm_service = LLMService()
