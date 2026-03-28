import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db import crud
from config import settings

router = APIRouter(tags=["profiles"])


@router.get("/")
async def list_profiles(db: AsyncSession = Depends(get_db)):
    profiles = await crud.get_profiles(db)
    return [
        {
            "id": p.id,
            "name": p.name,
            "avatar_path": p.avatar_path,
            "has_voice": p.voice_embedding is not None,
            "notes": (p.preferences or {}).get("notes", ""),
            "created_at": p.created_at.isoformat(),
        }
        for p in profiles
    ]


@router.post("/")
async def create_profile(body: dict, db: AsyncSession = Depends(get_db)):
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    profile = await crud.create_profile(db, name)
    return {"id": profile.id, "name": profile.name}


@router.post("/{profile_id}/avatar")
async def upload_avatar(
    profile_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    profile = await crud.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")

    os.makedirs(settings.avatar_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".jpg"
    filename = f"{profile_id}{ext}"
    path = os.path.join(settings.avatar_dir, filename)

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    profile.avatar_path = f"/data/avatars/{filename}"
    await db.commit()
    return {"avatar_path": profile.avatar_path}


@router.patch("/{profile_id}")
async def update_profile(profile_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    profile = await crud.get_profile(db, profile_id)
    if not profile:
        raise HTTPException(404, "Profile not found")
    if "name" in body and (body["name"] or "").strip():
        profile.name = body["name"].strip()
    if "notes" in body:
        prefs = dict(profile.preferences or {})
        prefs["notes"] = body["notes"]
        profile.preferences = prefs
    await db.commit()
    return {"ok": True}


@router.delete("/{profile_id}")
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    await crud.delete_profile(db, profile_id)
    return {"ok": True}
