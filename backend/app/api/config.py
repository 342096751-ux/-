from fastapi import APIRouter

from app.api.deps import config_manager
from app.models.config import SystemConfig

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=SystemConfig)
async def get_system_config() -> SystemConfig:
    return config_manager.get()


@router.put("", response_model=SystemConfig)
async def update_system_config(payload: SystemConfig) -> SystemConfig:
    return config_manager.update(payload)

