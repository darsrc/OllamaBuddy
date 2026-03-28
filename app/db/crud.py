import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.models import UserProfile, Conversation, Message


# ── Profiles ───────────────────────────────────────────────────────────────

async def get_profiles(db: AsyncSession) -> list[UserProfile]:
    result = await db.execute(select(UserProfile).order_by(UserProfile.created_at))
    return list(result.scalars().all())


async def get_profile(db: AsyncSession, profile_id: str) -> UserProfile | None:
    result = await db.execute(
        select(UserProfile).where(UserProfile.id == profile_id)
    )
    return result.scalar_one_or_none()


async def create_profile(
    db: AsyncSession, name: str, avatar_path: str | None = None
) -> UserProfile:
    profile = UserProfile(id=str(uuid.uuid4()), name=name, avatar_path=avatar_path)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def update_profile_embedding(
    db: AsyncSession, profile_id: str, embedding: list[float]
) -> bool:
    profile = await get_profile(db, profile_id)
    if not profile:
        return False
    profile.voice_embedding = embedding
    await db.commit()
    return True


async def delete_profile(db: AsyncSession, profile_id: str):
    profile = await get_profile(db, profile_id)
    if profile:
        await db.delete(profile)
        await db.commit()


async def get_all_voice_profiles(db: AsyncSession) -> list[UserProfile]:
    result = await db.execute(
        select(UserProfile).where(UserProfile.voice_embedding.is_not(None))
    )
    return list(result.scalars().all())


# ── Conversations ──────────────────────────────────────────────────────────

async def get_conversations(db: AsyncSession, limit: int = 50) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).order_by(desc(Conversation.updated_at)).limit(limit)
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: str) -> Conversation | None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id)
    )
    return result.scalar_one_or_none()


async def create_conversation(
    db: AsyncSession,
    model: str,
    system_prompt: str = "You are a helpful assistant.",
    profile_id: str | None = None,
    title: str = "New Conversation",
) -> Conversation:
    conv = Conversation(
        id=str(uuid.uuid4()),
        model=model,
        system_prompt=system_prompt,
        profile_id=profile_id,
        title=title,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def update_conversation_title(db: AsyncSession, conv_id: str, title: str):
    conv = await get_conversation(db, conv_id)
    if conv:
        conv.title = title
        await db.commit()


async def delete_conversation(db: AsyncSession, conv_id: str):
    # Delete messages first, then conversation
    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id)
    )
    for msg in result.scalars().all():
        await db.delete(msg)
    conv = await get_conversation(db, conv_id)
    if conv:
        await db.delete(conv)
    await db.commit()


# ── Messages ───────────────────────────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    speaker_id: str | None = None,
    speaker_confidence: float | None = None,
    tool_name: str | None = None,
) -> Message:
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        speaker_id=speaker_id,
        speaker_confidence=speaker_confidence,
        tool_name=tool_name,
    )
    db.add(msg)
    conv = await get_conversation(db, conversation_id)
    if conv:
        conv.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(db: AsyncSession, conversation_id: str) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())
