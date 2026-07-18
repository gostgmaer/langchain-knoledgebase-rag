import asyncio

from langchain_core.messages import HumanMessage

from packages.infrastructure.ai import LLMManager


async def main():

    llm = LLMManager()

    response = await llm.ainvoke(
        [
            HumanMessage(
                content="Say hello in one sentence."
            )
        ]
    )

    print(response)
    print(response.content)


asyncio.run(main())