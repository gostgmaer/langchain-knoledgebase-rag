from __future__ import annotations

from aiohttp.web_fileresponse import FileResponse
from fastapi import FastAPI, Path

from packages.api.exception_handlers import register_exception_handlers
from packages.api.lifespan import lifespan
from packages.api.middleware import register_middlewares
from packages.api.routers import register_routers
from packages.graph.builder import GraphBuilder


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """

    # graph = GraphBuilder.build()  # or however you access the compiled graph

    # png = graph.get_graph().draw_mermaid_png()

    # path = Path("graph.png")
    # path.write_bytes(png)



    app = FastAPI(
        title="EasyDev AI Platform",
        description="Production AI Platform powered by LangGraph",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    register_middlewares(app)
    register_exception_handlers(app)
    register_routers(app)

    return app


app = create_application()