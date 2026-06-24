import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from typing import Optional

import mlflow
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlmodel.ext.asyncio.session import AsyncSession

from app.resources.models import MessageRole
from app.resources.schemas import ChatRequest
from app.services.chat_graph import get_chat_graph
from app.services.conversation_service import (
    append_message,
    create_conversation,
    get_conversation_messages,
    update_title,
)
from app.services.guardrails import classify_message
from app.services.instruction_loader import load_instructions

logger = logging.getLogger(__name__)

_MAX_HISTORY = 100
_TRUNCATED_HISTORY = 50


_TASK_SIGNALS: dict[str, list[str]] = {
    "content-dev-workflow": [
        "content strategy", "content strategies", "content plan", "content planning",
        "editorial calendar", "content calendar", "content brief", "campaign brief",
        "content development", "research brief", "content workflow",
        "content structure", "variation plan", "execution checklist",
        "content audit", "content phase", "build a strategy", "develop a strategy",
    ],
    "seo-optimization": [
        "seo", "search engine", "meta description", "meta title", "page title",
        "keyword", "ranking", "organic traffic", "search optimization",
    ],
    "site-management": [
        "create a site", "create site", "new site", "set up a site", "provision a site",
        "add a site", "create a microsite", "deploy a site",
        "delete a site", "delete site", "remove a site", "remove site",
        "site template", "site language", "site collection",
        "list sites", "show sites", "available sites",
    ],
}


def _detect_task_name(message: str, history: list) -> Optional[str]:
    """Return the most appropriate task overlay name, or None."""
    search_text = message.lower()
    for msg in history[-6:]:
        search_text += " " + (msg.content or "").lower()
    for task, signals in _TASK_SIGNALS.items():
        if any(s in search_text for s in signals):
            return task
    return None


async def stream_chat(
    db: AsyncSession,
    user_id: str,
    request: ChatRequest,
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted event strings for the chat stream."""
    task_name: Optional[str] = None  # resolved after history is loaded

    try:
        _span_ctx = mlflow.start_span(
            name="chat_service.stream",
            attributes={
                "conversation_id": request.conversation_id or "new",
                "user_id": user_id,
                "guardrail_category": classify_message(request.message) or "",
            },
        )
    except Exception:
        _span_ctx = contextlib.nullcontext()

    with _span_ctx:
        # Resolve or create conversation
        if request.conversation_id:
            result = await get_conversation_messages(db, request.conversation_id, user_id)
            if result is None:
                yield _event({"type": "error", "code": "unauthorized"})
                return
            conversation, history = result
        else:
            conversation = await create_conversation(
                db, user_id, request.context.site_id
            )
            history = []

        conversation_id = conversation.id
        yield _event({"type": "conversationId", "id": conversation_id})

        # Persist user message
        await append_message(db, conversation_id, MessageRole.user, request.message)

        # Detect task overlay from current message + recent history
        task_name = _detect_task_name(request.message, history)

        # Build message list for LangGraph
        system_prompt = load_instructions(task_name)
        ctx = request.context

        # Empty string means the field was not available from the host environment.
        site_desc = f"`{ctx.site_id}`" if ctx.site_id else "**unknown** — call `list_sites` to discover available sites before attempting any site-scoped operation"
        page_desc = f"`{ctx.page_id}`" if ctx.page_id else "**not selected** — the user has not navigated to a page yet; ask them to select one in the Pages editor content tree, or use `search_pages` once a site is known"
        lang_desc = ctx.language or "en"

        user_lines = []
        if ctx.user_name:
            user_lines.append(f"You are helping **{ctx.user_name}**")
            if ctx.user_email:
                user_lines.append(f"({ctx.user_email})")
            user_lines.append(f"on site {site_desc}, page {page_desc}, language `{lang_desc}`.")
        else:
            user_lines.append(f"Current context: site {site_desc}, page {page_desc}, language `{lang_desc}`.")

        system_prompt += "\n\n## Session Context\n\n" + " ".join(user_lines)
        lc_messages = [SystemMessage(content=system_prompt)]

        # Truncate history if too long
        if len(history) > _MAX_HISTORY:
            history = history[-_TRUNCATED_HISTORY:]
        for msg in history:
            if msg.role == MessageRole.user:
                lc_messages.append(HumanMessage(content=msg.content))
            else:
                lc_messages.append(AIMessage(content=msg.content))
        lc_messages.append(HumanMessage(content=request.message))

        # Tools that mutate Sitecore Pages content — trigger a canvas reload when they complete
        _WRITE_TOOLS = frozenset({
            "create_page", "add_language_to_page", "add_component_on_page",
            "set_component_datasource", "create_component_ds",
            "create_content_item", "update_fields_on_item", "update_content",
            "delete_content", "update_asset", "create_perso_version",
            "create_perso_version_multi", "update_perso_version",
            "create_component_ab_test", "update_ab_test", "set_component_variant",
        })

        # Stream from LangGraph — 30 s timeout per event to detect hung tool calls
        full_response = ""
        write_occurred = False
        _auto_options_emitted: set[str] = set()  # first auto-options emission per tool wins per turn
        try:
            gen = get_chat_graph().astream_events(
                {"messages": lc_messages}, version="v2"
            )
            while True:
                try:
                    event = await asyncio.wait_for(gen.__anext__(), timeout=360.0)
                except asyncio.TimeoutError:
                    yield _event({"type": "error", "code": "timeout"})
                    return
                except StopAsyncIteration:
                    break

                evt = event["event"]
                if evt == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    text = chunk.content if hasattr(chunk, "content") else ""
                    if text:
                        full_response += text
                        yield _event({"type": "delta", "text": text})
                elif evt == "on_tool_start":
                    yield _event({"type": "tool_start", "tool": event.get("name", "")})
                elif evt == "on_tool_end":
                    tool_name = event.get("name", "")
                    yield _event({"type": "tool_end", "tool": tool_name})
                    if tool_name in _WRITE_TOOLS:
                        write_occurred = True
                    _AUTO_OPTIONS_TOOLS = {
                        "search_site_images",
                        "present_options",
                        "get_site_templates",
                        "get_environment_languages",
                        "list_site_collections",
                    }
                    if tool_name == "create_marketing_site":
                        raw = event.get("data", {}).get("output")
                        output = raw
                        if hasattr(raw, "content"):
                            try:
                                output = json.loads(raw.content)
                            except Exception:
                                output = {}
                        elif isinstance(raw, str):
                            try:
                                output = json.loads(raw)
                            except Exception:
                                output = {}
                        if isinstance(output, dict) and output.get("pending") and output.get("handle"):
                            yield _event({
                                "type": "job_started",
                                "handle": output["handle"],
                                "name": output.get("name", ""),
                            })
                    if tool_name in _AUTO_OPTIONS_TOOLS and (
                        tool_name in ("search_site_images", "present_options")
                        or not _auto_options_emitted
                    ):
                        raw = event.get("data", {}).get("output")
                        if tool_name == "search_site_images":
                            logger.info("search_site_images on_tool_end output type=%s value=%r", type(raw).__name__, str(raw)[:200])
                        # LangGraph may deliver the output as a dict, a JSON string, or a ToolMessage
                        output = raw
                        if hasattr(raw, "content"):
                            import json as _json
                            try:
                                output = _json.loads(raw.content)
                            except Exception:
                                output = {}
                        elif isinstance(raw, str):
                            import json as _json
                            try:
                                output = _json.loads(raw)
                            except Exception:
                                output = {}
                        if isinstance(output, dict):
                            if tool_name == "search_site_images" and output.get("success") and output.get("results"):
                                logger.info("Emitting image_results with %d items", len(output["results"]))
                                yield _event({
                                    "type": "image_results",
                                    "results": output["results"],
                                    "query": output.get("query", ""),
                                    "count": output.get("count", len(output["results"])),
                                })
                            elif tool_name == "present_options" and output.get("presented") and output.get("items"):
                                logger.info("Emitting options with %d items (type=%s)", len(output["items"]), output.get("option_type"))
                                yield _event({
                                    "type": "options",
                                    "items": output["items"],
                                    "prompt": output.get("prompt", ""),
                                    "option_type": output.get("option_type", "generic"),
                                    "count": output.get("count", len(output["items"])),
                                })
                            elif tool_name == "get_site_templates" and output.get("success") and output.get("templates"):
                                items = [
                                    {"id": t["template_id"], "label": t["template_name"], "description": t.get("description", "")}
                                    for t in output["templates"]
                                    if t.get("template_id") and t.get("template_name")
                                ]
                                if items:
                                    logger.info("Auto-emitting options for get_site_templates: %d items", len(items))
                                    _auto_options_emitted.add(tool_name)
                                    yield _event({
                                        "type": "options",
                                        "items": items,
                                        "prompt": "Which template would you like to use?",
                                        "option_type": "generic",
                                        "count": len(items),
                                    })
                            elif tool_name == "get_environment_languages" and output.get("success") and output.get("languages"):
                                items = [
                                    {"id": lang["isoCode"], "label": lang.get("label") or lang["isoCode"]}
                                    for lang in output["languages"]
                                    if lang.get("isoCode")
                                ]
                                if items:
                                    logger.info("Auto-emitting options for get_environment_languages: %d items", len(items))
                                    _auto_options_emitted.add(tool_name)
                                    yield _event({
                                        "type": "options",
                                        "items": items,
                                        "prompt": "Which primary language would you like for this site?",
                                        "option_type": "generic",
                                        "count": len(items),
                                    })
                            elif tool_name == "list_site_collections" and output.get("success") and output.get("collections"):
                                items = [
                                    {"id": c["id"], "label": c["name"]}
                                    for c in output["collections"]
                                    if c.get("id") and c.get("name")
                                ]
                                if items:
                                    logger.info("Auto-emitting options for list_site_collections: %d items", len(items))
                                    _auto_options_emitted.add(tool_name)
                                    yield _event({
                                        "type": "options",
                                        "items": items,
                                        "prompt": "Which collection should the site belong to?",
                                        "option_type": "generic",
                                        "count": len(items),
                                    })
        except Exception as exc:
            code = _map_error(exc)
            yield _event({"type": "error", "code": code})
            return

        if write_occurred:
            yield _event({"type": "canvas_reload"})

        # Persist assistant message
        await append_message(db, conversation_id, MessageRole.assistant, full_response)

        # Auto-title first message
        if not history and full_response:
            asyncio.create_task(
                _auto_title(conversation_id, request.message)
            )

        yield _event({"type": "done"})


async def _auto_title(conversation_id: str, first_message: str) -> None:
    from app.resources.database import _get_session_factory

    title = first_message[:60].strip()
    if len(first_message) > 60:
        title += "…"
    try:
        async with _get_session_factory()() as db:
            await update_title(db, conversation_id, title)
    except Exception:
        pass


def _event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _map_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    if "ratelimit" in name:
        return "rate_limit"
    if "timeout" in name:
        return "timeout"
    if "authentication" in name or "api" in name:
        return "upstream_error"
    logger.exception("Unexpected error in chat stream: %s", exc)
    return "internal_error"
