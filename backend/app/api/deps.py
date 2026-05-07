from pathlib import Path

from app.core.config_manager import ConfigManager
from app.core.knowledge_manager import KnowledgeManager
from app.services.knowledge_service import KnowledgeService
from app.services.vector_store import VectorStore

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

config_manager = ConfigManager(DATA_DIR)
vector_store = VectorStore()
knowledge_service = KnowledgeService(vector_store)
knowledge_manager = KnowledgeManager(knowledge_service)

