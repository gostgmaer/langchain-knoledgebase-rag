# Router agents
from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from packages.api.dependencies import (
    DEFAULT_TENANT_ID,
    get_scoped_container,
    require_uuid_header,
)
from packages.api.responses import ApiResponse
from packages.api.schemas.agent import (
    AgentListResponseSchema,
    AgentResponseSchema,
    CreateAgentRequestSchema,
)
from packages.domain.enums.agent_status import AgentStatus
from packages.domain.models.agent import Agent
from packages.infrastructure.container import ApplicationContainer

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agent"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=ApiResponse[AgentResponseSchema],
    summary="Create an agent",
    description="Creates a new agent for the calling tenant, referencing an existing model profile.",
)
async def create_agent(
    payload: CreateAgentRequestSchema,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    agents = container.repositories.agent()
    model_profiles = container.repositories.model_profile()

    existing = await agents.get_by_tenant_and_name(tenant_id, payload.name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An agent named '{payload.name}' already exists for this tenant.",
        )

    model_profile = await model_profiles.get(payload.model_profile_id)
    if model_profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model profile '{payload.model_profile_id}' does not exist.",
        )

    agent = Agent(
        tenant_id=tenant_id,
        name=payload.name,
        slug=_slugify(payload.name),
        description=payload.description,
        system_prompt=payload.system_prompt,
        llm_provider=payload.llm_provider,
        llm_model=payload.llm_model,
        model_profile_id=payload.model_profile_id,
        temperature=payload.temperature,
        top_p=payload.top_p,
        max_tokens=payload.max_tokens,
        is_active=True,
        status=AgentStatus.ACTIVE,
    )

    created = await agents.create(agent)

    return ApiResponse(
        message="Agent created.",
        data=AgentResponseSchema.model_validate(created),
    )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[AgentListResponseSchema],
    summary="List agents",
    description="Lists the calling tenant's agents, any status.",
)
async def list_agents(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    agents = container.repositories.agent()

    total = await agents.count_by_tenant(tenant_id)
    rows = await agents.list_by_tenant(tenant_id, limit=limit, offset=offset)

    return ApiResponse(
        message="Agents retrieved.",
        data=AgentListResponseSchema(
            total=total,
            limit=limit,
            offset=offset,
            agents=[AgentResponseSchema.model_validate(a) for a in rows],
        ),
    )


@router.get(
    "/{agent_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApiResponse[AgentResponseSchema],
    summary="Fetch an agent",
    description="Fetches a single agent's configuration by ID.",
)
async def get_agent(
    agent_id: UUID,
    request: Request,
    container: ApplicationContainer = Depends(get_scoped_container),
):
    tenant_id = require_uuid_header(request, "X-Tenant-ID", default=DEFAULT_TENANT_ID)

    agents = container.repositories.agent()
    agent = await agents.get(agent_id)

    if agent is None or agent.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found.",
        )

    return ApiResponse(
        message="Agent retrieved.",
        data=AgentResponseSchema.model_validate(agent),
    )
