from fastapi import APIRouter, HTTPException, Query

from app.api.deps import knowledge_manager
from app.models.knowledge import KnowledgeCreate, KnowledgeItem, KnowledgeUpdate

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeItem])
async def list_knowledge(query: str | None = Query(default=None)) -> list[KnowledgeItem]:
    if query:
        return knowledge_manager.search(query=query, limit=5)
    return knowledge_manager.list()


@router.post("", response_model=KnowledgeItem)
async def create_knowledge(payload: KnowledgeCreate) -> KnowledgeItem:
    return knowledge_manager.create(payload)


@router.put("/{item_id}", response_model=KnowledgeItem)
async def update_knowledge(item_id: str, payload: KnowledgeUpdate) -> KnowledgeItem:
    try:
        return knowledge_manager.update(item_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{item_id}")
async def delete_knowledge(item_id: str) -> dict[str, str]:
    try:
        knowledge_manager.delete(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "ok"}

