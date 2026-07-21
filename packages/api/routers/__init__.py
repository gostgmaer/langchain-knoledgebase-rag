# API routers init
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI

from packages.api.routers.chat import router as chat_router
from packages.api.routers.conversations import router as conversation_router

# from .documents import router as document_router
# from .feedback import router as feedback_router
from packages.api.routers.health import router as health_router
from packages.api.security import get_bearer_token, get_tenant_id

# from .knowledge_bases import router as knowledge_base_router
# from .models import router as model_router
# from .prompts import router as prompt_router
# from .search import router as search_router
# from .tools import router as tool_router
api_router = APIRouter(
        prefix="/api/v1",
        dependencies=[
            Depends(get_tenant_id),
            Depends(get_bearer_token),
        ],
    )

# api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(conversation_router)
# api_router.include_router(knowledge_base_router)
# api_router.include_router(document_router)
# api_router.include_router(search_router)
# api_router.include_router(prompt_router)
# api_router.include_router(model_router)
# api_router.include_router(tool_router)
# api_router.include_router(feedback_router)


def register_routers(app: FastAPI) -> None:
    """
    Register all application routers.
    """
    app.include_router(api_router)
