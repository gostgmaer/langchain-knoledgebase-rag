# Application module
from packages.chat.chat_service import ChatService
from packages.graph.manager import GraphManager
from packages.conversation.manager import ConversationManager
from packages.conversation.memory_store import MemoryConversationStore


class Application:

    def __init__(self):

        self.chat_service = ChatService()

        self.graph_manager = GraphManager(
            chat_service=self.chat_service,
        )

        self.conversation_store = MemoryConversationStore()

        self.conversation_manager = ConversationManager(
            graph=self.graph_manager,
            store=self.conversation_store,
        )