import asyncio
import json
import logging
import struct
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.database import AsyncSessionLocal
from app.db import crud
from app.services.llm_service import llm_service
from app.services.speaker_service import speaker_service
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service
from app.session.manager import session_manager
from app.session.state import SessionState
from app.session.tts_chunker import TTSChunker
from config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Entry point ─────────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_id = str(uuid.uuid4())
    session = session_manager.create(ws_id, ws)
    session.tts_chunker = TTSChunker(mode=settings.default_tts_mode)
    session.settings.model = settings.default_model
    session.settings.tts_voice = settings.default_voice
    session.settings.tts_speed = settings.default_tts_speed
    session.settings.tts_mode = settings.default_tts_mode

    # Persist initial conversation
    async with AsyncSessionLocal() as db:
        conv = await crud.create_conversation(
            db, model=settings.default_model
        )
        session.conversation_id = conv.id

    # Greet with session_ready
    await ws.send_json(
        {
            "type": "session_ready",
            "session_id": ws_id,
            "conversation_id": session.conversation_id,
            "available_models": await _list_ollama_models(),
            "available_voices": tts_service.available_voices,
            "settings": _settings_dict(session.settings),
        }
    )

    try:
        while True:
            raw = await ws.receive()
            if "text" in raw:
                try:
                    msg = json.loads(raw["text"])
                    await _dispatch_control(session, ws, msg)
                except json.JSONDecodeError:
                    pass
            elif "bytes" in raw:
                await _dispatch_audio(session, ws, raw["bytes"])
    except WebSocketDisconnect:
        logger.info(f"WS {ws_id} disconnected")
    except Exception as e:
        logger.error(f"WS {ws_id} error: {e}")
    finally:
        await session_manager.interrupt_session(ws_id)
        session_manager.remove(ws_id)


# ── Control message dispatcher ───────────────────────────────────────────────

async def _dispatch_control(session, ws: WebSocket, msg: dict):
    t = msg.get("type")

    if t == "recording_start":
        session.audio_buffer.clear()
        if session.enrollment_mode:
            session.state = SessionState.ENROLLING
        else:
            session.state = SessionState.LISTENING
        await ws.send_json({"type": "state_change", "state": session.state.value})

    elif t == "recording_stop":
        # Actual processing triggered by AUDIO_FINAL binary frame
        pass

    elif t == "text_input":
        text = (msg.get("text") or "").strip()
        if text and session.state == SessionState.IDLE:
            await _run_turn(session, ws, text)

    elif t == "interrupt":
        await session_manager.interrupt_session(session.ws_id)
        session.interrupt_event.clear()
        session.state = SessionState.IDLE
        await ws.send_json({"type": "interrupted"})
        await ws.send_json({"type": "state_change", "state": "idle"})

    elif t == "settings_update":
        s = session.settings
        s.model = msg.get("model", s.model)
        s.temperature = float(msg.get("temperature", s.temperature))
        s.top_p = float(msg.get("top_p", s.top_p))
        s.num_ctx = int(msg.get("num_ctx", s.num_ctx))
        s.system_prompt = msg.get("system_prompt", s.system_prompt)
        s.tts_voice = msg.get("tts_voice", s.tts_voice)
        s.tts_mode = msg.get("tts_mode", s.tts_mode)
        s.tts_speed = float(msg.get("tts_speed", s.tts_speed))
        s.voice_id_enabled = bool(msg.get("voice_id_enabled", s.voice_id_enabled))
        s.search_enabled = bool(msg.get("search_enabled", s.search_enabled))
        if session.tts_chunker:
            session.tts_chunker.set_mode(s.tts_mode)

    elif t == "new_conversation":
        async with AsyncSessionLocal() as db:
            conv = await crud.create_conversation(
                db,
                model=session.settings.model,
                system_prompt=session.settings.system_prompt,
            )
            session.conversation_id = conv.id
            session.messages.clear()
        await ws.send_json(
            {"type": "new_conversation", "conversation_id": session.conversation_id}
        )

    elif t == "load_conversation":
        conv_id = msg.get("conversation_id")
        if conv_id:
            async with AsyncSessionLocal() as db:
                db_msgs = await crud.get_messages(db, conv_id)
                session.conversation_id = conv_id
                session.messages = [
                    {"role": m.role, "content": m.content}
                    for m in db_msgs
                    if m.role in ("user", "assistant")
                ]
            await ws.send_json(
                {
                    "type": "conversation_loaded",
                    "conversation_id": conv_id,
                    "messages": session.messages,
                }
            )

    elif t == "start_enrollment":
        session.enrollment_mode = True
        session.enrollment_samples.clear()
        session.enrollment_profile_id = msg.get("profile_id")
        await ws.send_json({"type": "enrollment_started"})

    elif t == "cancel_enrollment":
        session.enrollment_mode = False
        session.enrollment_samples.clear()
        session.state = SessionState.IDLE
        await ws.send_json({"type": "state_change", "state": "idle"})

    elif t == "enroll_speaker":
        profile_id = msg.get("profile_id")
        if profile_id and session.enrollment_samples:
            await _finish_enrollment(session, ws, profile_id)

    elif t == "ping":
        await ws.send_json({"type": "pong"})


# ── Audio frame dispatcher ───────────────────────────────────────────────────

async def _dispatch_audio(session, ws: WebSocket, data: bytes):
    if len(data) < 4:
        return
    tag = struct.unpack_from("<I", data, 0)[0]
    payload = data[4:]

    if tag == 0x10:   # AUDIO_CHUNK
        session.audio_buffer.append(payload)

    elif tag == 0x11:   # AUDIO_FINAL
        if payload:
            session.audio_buffer.append(payload)
        if not session.audio_buffer:
            return
        combined = b"".join(session.audio_buffer)
        session.audio_buffer.clear()

        if session.enrollment_mode:
            await _handle_enrollment_audio(session, ws, combined)
        else:
            await _transcribe_and_respond(session, ws, combined)


# ── Enrollment ───────────────────────────────────────────────────────────────

async def _handle_enrollment_audio(session, ws: WebSocket, audio: bytes):
    session.enrollment_samples.append(audio)
    n = len(session.enrollment_samples)
    needed = settings.enrollment_samples_required

    await ws.send_json(
        {"type": "enrollment_progress", "samples_collected": n, "samples_needed": needed}
    )

    if n >= needed and session.enrollment_profile_id:
        await _finish_enrollment(session, ws, session.enrollment_profile_id)


async def _finish_enrollment(session, ws: WebSocket, profile_id: str):
    embedding = await speaker_service.enroll(session.enrollment_samples)
    if embedding is not None:
        async with AsyncSessionLocal() as db:
            await crud.update_profile_embedding(db, profile_id, embedding.tolist())
        await ws.send_json({"type": "enrollment_done", "profile_id": profile_id})
    else:
        await ws.send_json(
            {"type": "error", "code": "ENROLL_FAILED", "message": "Enrollment failed"}
        )
    session.enrollment_samples.clear()
    session.enrollment_mode = False
    session.state = SessionState.IDLE
    await ws.send_json({"type": "state_change", "state": "idle"})


# ── STT → LLM pipeline ───────────────────────────────────────────────────────

async def _transcribe_and_respond(session, ws: WebSocket, audio: bytes):
    session.state = SessionState.TRANSCRIBING
    await ws.send_json({"type": "state_change", "state": "transcribing"})

    # Optional speaker ID
    speaker_match = None
    if session.settings.voice_id_enabled and speaker_service.available:
        speaker_match = await _identify_speaker(session, ws, audio)

    # Collect partials via callback
    async def _on_partial(text: str):
        try:
            await ws.send_json(
                {"type": "transcript_partial", "text": text, "is_final": False}
            )
        except Exception:
            pass

    transcript = await stt_service.transcribe(audio, on_partial=_on_partial)

    if not transcript:
        session.state = SessionState.IDLE
        await ws.send_json({"type": "state_change", "state": "idle"})
        return

    msg_id = str(uuid.uuid4())
    await ws.send_json(
        {
            "type": "transcript_final",
            "text": transcript,
            "speaker_id": speaker_match.label if speaker_match else None,
            "speaker_confidence": (
                round(speaker_match.confidence, 3) if speaker_match else None
            ),
            "message_id": msg_id,
        }
    )

    # Persist user message
    async with AsyncSessionLocal() as db:
        await crud.add_message(
            db,
            conversation_id=session.conversation_id,
            role="user",
            content=transcript,
            speaker_id=speaker_match.profile_id if speaker_match else None,
            speaker_confidence=speaker_match.confidence if speaker_match else None,
        )
        # Auto-title on first message
        if not session.messages:
            title = transcript[:60] + ("…" if len(transcript) > 60 else "")
            await crud.update_conversation_title(db, session.conversation_id, title)

    await _run_turn(session, ws, transcript, speaker_match)


async def _identify_speaker(session, ws: WebSocket, audio: bytes):
    from app.services.speaker_service import SpeakerMatch

    embedding = await speaker_service.embed_utterance(audio)
    if embedding is None:
        return None

    async with AsyncSessionLocal() as db:
        profiles = await crud.get_all_voice_profiles(db)

    import numpy as np

    best_score, best_profile = 0.0, None
    for profile in profiles:
        if not profile.voice_embedding:
            continue
        stored = np.array(profile.voice_embedding)
        score = speaker_service.cosine_similarity(embedding, stored)
        if score > best_score:
            best_score, best_profile = score, profile

    if best_profile and best_score >= settings.speaker_threshold:
        match = SpeakerMatch(
            profile_id=best_profile.id,
            label=best_profile.name,
            confidence=best_score,
        )
        await ws.send_json(
            {
                "type": "speaker_identified",
                "profile_id": match.profile_id,
                "label": match.label,
                "confidence": round(match.confidence, 3),
                "is_enrolled": True,
            }
        )
        return match
    return None


async def _run_turn(session, ws: WebSocket, text: str, speaker_match=None):
    if session.state not in (SessionState.IDLE, SessionState.TRANSCRIBING):
        return
    session.interrupt_event.clear()

    session.llm_task = asyncio.create_task(
        llm_service.run_turn(
            session,
            ws,
            text,
            speaker_id=speaker_match.label if speaker_match else None,
        )
    )
    try:
        await session.llm_task
    except asyncio.CancelledError:
        logger.info(f"LLM task cancelled ({session.ws_id})")
    except Exception as e:
        logger.error(f"LLM task error ({session.ws_id}): {e}")
        await ws.send_json({"type": "error", "code": "LLM_ERROR", "message": str(e)})

    # Persist assistant reply
    if session.messages and session.messages[-1]["role"] == "assistant":
        async with AsyncSessionLocal() as db:
            await crud.add_message(
                db,
                conversation_id=session.conversation_id,
                role="assistant",
                content=session.messages[-1]["content"],
            )

    if not session.interrupt_event.is_set():
        session.state = SessionState.IDLE
        await ws.send_json({"type": "state_change", "state": "idle"})


# ── Helpers ─────────────────────────────────────────────────────────────────

async def _list_ollama_models() -> list[str]:
    try:
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host)
        resp = await client.list()
        return [m.model for m in resp.models]
    except Exception:
        return []


def _settings_dict(s) -> dict:
    return {
        "model": s.model,
        "temperature": s.temperature,
        "top_p": s.top_p,
        "num_ctx": s.num_ctx,
        "system_prompt": s.system_prompt,
        "tts_voice": s.tts_voice,
        "tts_mode": s.tts_mode,
        "tts_speed": s.tts_speed,
        "voice_id_enabled": s.voice_id_enabled,
        "search_enabled": s.search_enabled,
    }
