import logging
import os
from contextlib import asynccontextmanager

import mlflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # MLflow auto-tracing
    try:
        mlflow.langchain.autolog()
    except Exception:
        pass

    # MCP tool initialisation — load each server independently so one failure
    # doesn't prevent other servers' tools from loading.
    mcp_client = None
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        from app.clients.mcp_client import build_mcp_server_config
        from app.clients.tools import set_mcp_tools
        from app.services.chat_graph import build_chat_graph

        servers = await build_mcp_server_config()
        all_tools = []
        working_servers: dict = {}

        for name, config in servers.items():
            try:
                client = MultiServerMCPClient({name: config})
                server_tools = await client.get_tools()
                all_tools.extend(server_tools)
                working_servers[name] = config
                logger.info("MCP server %r loaded %d tools", name, len(server_tools))
            except Exception as exc:
                logger.warning("MCP server %r skipped (%s)", name, exc)

        if all_tools:
            mcp_client = MultiServerMCPClient(working_servers)
            set_mcp_tools(all_tools)
            build_chat_graph()
            logger.info(
                "MCP tools loaded (%d total from %d servers): %s",
                len(all_tools),
                len(working_servers),
                [t.name for t in all_tools],
            )
        else:
            logger.warning("No MCP servers available — running without MCP tools")
    except Exception as exc:
        logger.warning("MCP initialisation failed — running without MCP tools: %s", exc, exc_info=True)

    # Keep the client alive so tools can create sessions when invoked
    app.state.mcp_client = mcp_client

    yield

    app.state.mcp_client = None


app = FastAPI(lifespan=lifespan)

_allowed_origins = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,https://localhost:3000,https://pages.sitecorecloud.io",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(auth_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/tools")
async def health_tools() -> dict:
    from app.clients.tools import get_all_tools

    tools = get_all_tools()
    return {
        "tool_count": len(tools),
        "tools": [{"name": t.name, "description": (t.description or "")[:120]} for t in tools],
    }
