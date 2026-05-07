from fastapi import APIRouter, HTTPException

from app.api.deps import config_manager
from app.models.config import AgentConfig

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentConfig])
async def list_agents() -> list[AgentConfig]:
    config = config_manager.get()
    return list(config.agents.values())


@router.put("/{agent_name}", response_model=AgentConfig)
async def update_agent(agent_name: str, payload: AgentConfig) -> AgentConfig:
    config = config_manager.get()
    if agent_name not in config.agents:
        raise HTTPException(status_code=404, detail="Agent not found")
    config.agents[agent_name] = payload
    config_manager.update(config)
    return payload

