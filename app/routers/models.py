from fastapi import APIRouter, HTTPException

from config import settings

router = APIRouter(tags=["models"])


@router.get("/")
async def list_models():
    try:
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host)
        resp = await client.list()
        return {"models": [m.model for m in resp.models]}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.post("/pull")
async def pull_model(body: dict):
    model = (body.get("model") or "").strip()
    if not model:
        raise HTTPException(400, "model name required")
    try:
        import ollama

        client = ollama.AsyncClient(host=settings.ollama_host)
        await client.pull(model)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
