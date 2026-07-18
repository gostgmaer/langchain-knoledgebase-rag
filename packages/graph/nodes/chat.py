# Chat node
from packages.chat import ChatService

chat_service = ChatService()


def chat_node(state):
    response = chat_service.chat(
        request={
            "messages": state["messages"]
        }
    )

    return {
        "messages": [response.message]
    }