from langchain_core.messages import BaseMessage, SystemMessage

from packages.graph.state import GraphState

class PromptBuilder:

    def build(
        self,
        state: GraphState,
    ) -> list[BaseMessage]:

        messages = list(state["messages"])

        system_messages: list[SystemMessage] = []

        if state.get("system_prompt"):
            system_messages.append(
                SystemMessage(content=state["system_prompt"])
            )

        documents = state.get("documents")

        if documents:

            context = "\n\n".join(
                document.page_content
                for document in documents
            )

            system_messages.append(
                SystemMessage(
                    content=f"Context:\n{context}"
                )
            )

        return [
            *system_messages,
            *messages,
        ]