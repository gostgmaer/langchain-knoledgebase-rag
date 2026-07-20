# Default ModelProfile/Agent/Conversation provisioning
from __future__ import annotations

from uuid import UUID

from packages.config.loader import settings
from packages.domain.enums.agent_status import AgentStatus
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.enums.model_provider import ModelProvider
from packages.domain.enums.model_status import ModelStatus
from packages.domain.models.agent import Agent
from packages.domain.models.conversation import Conversation
from packages.domain.models.model_profile import ModelProfile
from packages.infrastructure.repositories.agent import AgentRepository
from packages.infrastructure.repositories.conversation import ConversationRepository
from packages.infrastructure.repositories.model_profile import ModelProfileRepository

DEFAULT_NAME = "default"

_PROVIDER_BY_NAME = {
    "google": ModelProvider.GOOGLE,
    "openai": ModelProvider.OPENAI,
    "anthropic": ModelProvider.ANTHROPIC,
    "groq": ModelProvider.GROQ,
}


async def ensure_default_model_profile(
    model_profiles: ModelProfileRepository,
) -> ModelProfile:
    """
    Returns the configured default ModelProfile, creating one from the
    app's AI settings (packages.config.ai) if none exists yet.
    """
    existing = await model_profiles.get_default()
    if existing is not None:
        return existing

    existing = await model_profiles.get_by_name(DEFAULT_NAME)
    if existing is not None:
        return existing

    provider = _PROVIDER_BY_NAME.get(
        settings.ai.default_provider.lower(),
        ModelProvider.CUSTOM,
    )

    profile = ModelProfile(
        name=DEFAULT_NAME,
        provider=provider,
        model=settings.ai.model,
        description="Auto-provisioned default profile, seeded from AI settings.",
        temperature=settings.ai.default_temperature,
        top_p=settings.ai.top_p,
        max_tokens=settings.ai.max_tokens,
        context_window=1_000_000,
        embedding_dimensions=settings.embedding.dimensions,
        vector=[0.0] * settings.embedding.dimensions,
        is_default=True,
        status=ModelStatus.ACTIVE,
    )

    return await model_profiles.create(profile)


async def ensure_default_agent(
    tenant_id: UUID,
    model_profile_id: UUID,
    agents: AgentRepository,
) -> Agent:
    """
    Returns this tenant's default Agent, creating one if none exists yet.
    Scoped per tenant_id — Agent has a required tenant_id column, so a
    single global default would leak one tenant's agent config to another.
    """
    existing = await agents.get_by_tenant_and_name(tenant_id, DEFAULT_NAME)
    if existing is not None:
        return existing

    agent = Agent(
        tenant_id=tenant_id,
        name=DEFAULT_NAME,
        slug=DEFAULT_NAME,
        description="Auto-provisioned default agent.",
        system_prompt="You are a helpful assistant.",
        llm_provider=settings.ai.default_provider,
        llm_model=settings.ai.model,
        temperature=settings.ai.default_temperature,
        top_p=settings.ai.top_p,
        max_tokens=settings.ai.max_tokens,
        is_active=True,
        status=AgentStatus.ACTIVE,
        model_profile_id=model_profile_id,
    )

    return await agents.create(agent)


async def ensure_default_conversation(
    tenant_id: UUID,
    user_id: UUID,
    agent_id: UUID,
    conversations: ConversationRepository,
) -> Conversation:
    """
    Returns this tenant+user's default Conversation, creating one if none
    exists yet. Keyed by a deterministic session_id so repeated calls
    (e.g. testing POST /api/v1/chat without a conversation_id) reuse the
    same conversation instead of creating a new one every time.
    """
    session_id = f"{DEFAULT_NAME}-{tenant_id}-{user_id}"

    existing = await conversations.get_by_session_id(session_id)
    if existing is not None:
        return existing

    conversation = Conversation(
        tenant_id=tenant_id,
        agent_id=agent_id,
        user_id=user_id,
        session_id=session_id,
        title="Default conversation",
        status=ConversationStatus.ACTIVE,
    )

    return await conversations.create(conversation)
