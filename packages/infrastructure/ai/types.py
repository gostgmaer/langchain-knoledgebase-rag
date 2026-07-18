from typing import TypeAlias

from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

Messages: TypeAlias = list[BaseMessage]

ChatModel: TypeAlias = BaseChatModel