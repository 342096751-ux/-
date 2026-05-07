from app.models.knowledge import KnowledgeCreate, KnowledgeItem, KnowledgeUpdate
from app.services.knowledge_service import KnowledgeService


class KnowledgeManager:
    def __init__(self, knowledge_service: KnowledgeService) -> None:
        self._knowledge_service = knowledge_service

    def list(self) -> list[KnowledgeItem]:
        return self._knowledge_service.list_items()

    def create(self, payload: KnowledgeCreate) -> KnowledgeItem:
        return self._knowledge_service.create_item(payload)

    def update(self, item_id: str, payload: KnowledgeUpdate) -> KnowledgeItem:
        return self._knowledge_service.update_item(item_id, payload)

    def delete(self, item_id: str) -> None:
        self._knowledge_service.delete_item(item_id)

    def search(self, query: str, limit: int = 3) -> list[KnowledgeItem]:
        return self._knowledge_service.search(query=query, limit=limit)

