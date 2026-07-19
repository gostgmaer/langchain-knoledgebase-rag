from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from packages.infrastructure.ai.prompts.context import PromptContext
from packages.infrastructure.ai.prompts.system import DEFAULT_SYSTEM_PROMPT


class PromptBuilder:

    def build(
        self,
        context: PromptContext,
    ) -> list[BaseMessage]:

        return [
            SystemMessage(
                content=DEFAULT_SYSTEM_PROMPT,
            ),
            HumanMessage(
                content=context.user_message.content,
            ),
        ]