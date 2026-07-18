import asyncio
from uuid import UUID
from packages.infrastructure.container.application import ApplicationContainer
from packages.domain.models.agent import Agent
from packages.domain.models.conversation import Conversation
from packages.domain.models.model_profile import ModelProfile
from packages.domain.enums.conversation_status import ConversationStatus
from packages.domain.enums.agent_status import AgentStatus
from packages.domain.enums.model_provider import ModelProvider

async def seed_conversation():
    # Initialize container to get DB session
    container = ApplicationContainer()
    engine = container.database.engine()
    session_factory = container.database.session_factory()

    target_conversation_id = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
    tenant_id = UUID("12345678-1234-5678-1234-567812345678")
    
    print("Seeding database...")
    async with session_factory() as session:
        # Check if conversation already exists
        result = await session.get(Conversation, target_conversation_id)
        if result:
            print("Conversation already exists! You're good to go.")
            return

        # Create dummy Tenant (if model exists, though Tenant isn't in models dir, Agent might not enforce FK)
        # We will just create a ModelProfile and Agent first.
        profile = ModelProfile(
            name="Default Profile",
            provider=ModelProvider.GOOGLE,
            model="gemini-3.1-flash-lite",
            context_window=128000,
            is_default=True
        )
        session.add(profile)
        await session.flush()

        agent = Agent(
            tenant_id=tenant_id,
            name="Test Agent",
            slug="test-agent",
            description="Agent for CLI testing",
            system_prompt="You are a helpful AI assistant.",
            llm_provider="GOOGLE",
            llm_model="gemini-3.1-flash-lite",
            status=AgentStatus.ACTIVE,
            model_profile_id=profile.id
        )
        session.add(agent)
        await session.flush()

        conversation = Conversation(
            id=target_conversation_id,
            tenant_id=tenant_id,
            agent_id=agent.id,
            user_id=tenant_id,
            session_id="test-session-1",
            title="CLI Test Conversation",
            status=ConversationStatus.ACTIVE
        )
        session.add(conversation)
        
        await session.commit()
        print(f"Successfully seeded Conversation ID: {target_conversation_id}")

if __name__ == "__main__":
    asyncio.run(seed_conversation())
