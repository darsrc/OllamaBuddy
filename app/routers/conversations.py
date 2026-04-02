from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import crud
from app.db.database import get_db

router = APIRouter(tags=["conversations"])


@router.get("/")
async def list_conversations(db: AsyncSession = Depends(get_db)):
    convs = await crud.get_conversations(db)
    return [
        {
            "id": c.id,
            "title": c.title,
            "model": c.model,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    conv = await crud.get_conversation(db, conv_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = await crud.get_messages(db, conv_id)
    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "system_prompt": conv.system_prompt,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "speaker_id": m.speaker_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    await crud.delete_conversation(db, conv_id)
    return {"ok": True}


@router.patch("/{conv_id}/title")
async def update_title(conv_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    await crud.update_conversation_title(db, conv_id, title)
    return {"ok": True}
