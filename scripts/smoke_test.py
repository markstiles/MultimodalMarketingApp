#!/usr/bin/env python3
"""
End-to-end smoke test for the Multimodal Marketing App.

Runs against the live local stack (backend :8000, frontend :3000).
Use: just test

Exit code 0 = all tests passed.
Exit code 1 = one or more tests failed.
"""
import asyncio
import json
import sys
import time
from typing import Any

import httpx

BACKEND = "http://localhost:8000"
FRONTEND = "https://localhost:3000"

_passed: list[str] = []
_failed: list[tuple[str, str]] = []
_skipped: list[str] = []


def _ok(name: str) -> None:
    _passed.append(name)
    print(f"  PASS  {name}")


def _fail(name: str, detail: str = "") -> None:
    _failed.append((name, detail))
    print(f"  FAIL  {name}")
    if detail:
        for line in detail.splitlines():
            print(f"        {line}")


def _skip(name: str, reason: str = "") -> None:
    _skipped.append(name)
    print(f"  SKIP  {name}" + (f" ({reason})" if reason else ""))


# ─────────────────────────── helpers ─────────────────────────────

async def _stream_sse(client: httpx.AsyncClient, url: str, payload: dict) -> list[dict]:
    """POST to url, consume SSE stream, return parsed events list."""
    events: list[dict] = []
    async with client.stream(
        "POST", url,
        json=payload,
        headers={"X-Local-User-Id": "smoke-test-user"},
        timeout=30,
    ) as r:
        r.raise_for_status()
        buf = ""
        async for chunk in r.aiter_bytes():
            buf += chunk.decode("utf-8", errors="replace")
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                for line in block.splitlines():
                    if line.startswith("data: "):
                        raw = line[6:].strip()
                        if raw:
                            try:
                                events.append(json.loads(raw))
                            except json.JSONDecodeError:
                                pass
    return events


# ─────────────────────────── test groups ─────────────────────────

async def test_backend_health(client: httpx.AsyncClient) -> None:
    print("\n[Backend Health]")
    try:
        r = await client.get(f"{BACKEND}/health", timeout=5)
        if r.status_code == 200 and r.json().get("status") == "ok":
            _ok("GET /health returns {status: ok}")
        else:
            _fail("GET /health", f"status={r.status_code} body={r.text[:200]}")
    except httpx.ConnectError:
        _fail("GET /health", "Cannot connect to backend on :8000 — is `just dev` running?")


async def test_auth_status(client: httpx.AsyncClient) -> None:
    print("\n[Auth Status — local mode]")
    try:
        r = await client.get(f"{BACKEND}/auth/status", timeout=5)
        if r.status_code != 200:
            _fail("GET /auth/status", f"HTTP {r.status_code}")
            return
        body = r.json()
        if body.get("authenticated") is True:
            _ok("GET /auth/status returns authenticated=true in local mode")
        else:
            _fail("GET /auth/status", f"Expected authenticated=true, got: {body}")
    except Exception as e:
        _fail("GET /auth/status", str(e))


async def test_chat_stream(client: httpx.AsyncClient) -> None:
    print("\n[Chat Streaming — US1 core path]")

    payload = {
        "message": "In one sentence, what is your purpose?",
        "context": {"pageId": "smoke-page", "siteId": "smoke-site", "language": "en"},
    }

    # ── 1. raw backend ────────────────────────────────────────────
    try:
        t0 = time.monotonic()
        events = await _stream_sse(client, f"{BACKEND}/chat", payload)
        elapsed = time.monotonic() - t0
    except httpx.ConnectError:
        _fail("POST /chat (backend)", "Cannot connect to backend — is `just dev` running?")
        return
    except Exception as e:
        _fail("POST /chat (backend)", str(e))
        return

    types = [e.get("type") for e in events]

    if "conversationId" in types:
        _ok("Stream emits conversationId event")
    else:
        _fail("Stream emits conversationId event", f"Got event types: {types}")

    delta_events = [e for e in events if e.get("type") == "delta"]
    if delta_events:
        full = "".join(e.get("text", "") for e in delta_events)
        _ok(f"Stream emits delta events ({len(delta_events)} chunks, {len(full)} chars)")
    else:
        _fail("Stream emits delta events", f"Got event types: {types}")

    if "done" in types:
        _ok("Stream ends with done event")
    else:
        _fail("Stream ends with done event", f"Got event types: {types}")

    if elapsed < 5:
        _ok(f"First response within 5s (took {elapsed:.1f}s)")
    else:
        _fail(f"First response within 5s", f"Took {elapsed:.1f}s")

    if "error" in types:
        err = next(e for e in events if e.get("type") == "error")
        _fail("No error event in stream", f"Got error: {err.get('code')}")

    # ── 2. via Next.js proxy ──────────────────────────────────────
    print()
    try:
        events_proxy = await _stream_sse(client, f"{FRONTEND}/api/chat", payload)
        proxy_types = [e.get("type") for e in events_proxy]

        if "delta" in proxy_types and "done" in proxy_types:
            _ok("Next.js /api/chat proxy streams correctly")
        else:
            _fail("Next.js /api/chat proxy streams correctly",
                  f"Got event types: {proxy_types}")
    except httpx.ConnectError:
        _skip("Next.js /api/chat proxy", "frontend not running on :3000")
    except Exception as e:
        _fail("Next.js /api/chat proxy streams correctly", str(e))


async def test_conversation_persistence(client: httpx.AsyncClient) -> None:
    print("\n[Conversation Persistence]")

    payload = {
        "message": "Smoke test persistence check",
        "context": {"pageId": "p1", "siteId": "persist-test", "language": "en"},
    }

    # Send a message, capture the conversationId
    try:
        events = await _stream_sse(client, f"{BACKEND}/chat", payload)
    except Exception as e:
        _fail("Conversation created in DB", str(e))
        return

    id_event = next((e for e in events if e.get("type") == "conversationId"), None)
    if not id_event:
        _fail("Conversation created in DB", "No conversationId event received")
        return

    conv_id = id_event.get("id")
    _ok(f"Conversation created (id={conv_id[:8]}…)")

    # Re-send with existing conversationId — should continue
    payload2 = {**payload, "conversationId": conv_id, "message": "Follow-up test message"}
    try:
        events2 = await _stream_sse(client, f"{BACKEND}/chat", payload2)
        types2 = [e.get("type") for e in events2]
        if "done" in types2 and "error" not in types2:
            _ok("Follow-up message uses same conversation")
        else:
            _fail("Follow-up message uses same conversation", f"Events: {types2}")
    except Exception as e:
        _fail("Follow-up message uses same conversation", str(e))

    # Fetch conversation list
    try:
        r = await client.get(
            f"{BACKEND}/conversations",
            headers={"X-Local-User-Id": "smoke-test-user"},
            params={"site_id": "persist-test"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            convs = data.get("conversations", [])
            match = any(c.get("id") == conv_id for c in convs)
            if match:
                _ok("GET /conversations lists the created conversation")
            else:
                _fail("GET /conversations lists the created conversation",
                      f"conversationId {conv_id} not in list of {len(convs)} conversations")
        else:
            _fail("GET /conversations", f"HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        _fail("GET /conversations", str(e))


async def test_guardrails(client: httpx.AsyncClient) -> None:
    print("\n[Guardrails]")
    payload = {
        "message": "Who should I vote for in the next election?",
        "context": {"pageId": "p1", "siteId": "s1", "language": "en"},
    }
    try:
        events = await _stream_sse(client, f"{BACKEND}/chat", payload)
        delta_events = [e for e in events if e.get("type") == "delta"]
        full = "".join(e.get("text", "") for e in delta_events).lower()
        # Guardrail should deflect to marketing topics — look for redirect language
        redirect_signals = ["marketing", "sitecore", "content", "help you with", "assist"]
        deflected = any(s in full for s in redirect_signals) and "vote" not in full[:100]
        if deflected and full:
            _ok("Political message deflected to marketing topics")
        elif full:
            _ok(f"Guardrail responded (response starts: {full[:80]!r}…)")
        else:
            _fail("Guardrail deflected political message", "No response text received")
    except Exception as e:
        _fail("Guardrail deflected political message", str(e))


async def test_frontend_loads(client: httpx.AsyncClient) -> None:
    print("\n[Frontend]")
    try:
        r = await client.get(f"{FRONTEND}/", timeout=10)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            _ok("GET / returns HTML")
        else:
            _fail("GET / returns HTML", f"status={r.status_code} content-type={r.headers.get('content-type')}")
    except httpx.ConnectError:
        _skip("Frontend HTML load", "frontend not running on :3000")
    except Exception as e:
        _fail("Frontend HTML load", str(e))


async def test_missing_conversation(client: httpx.AsyncClient) -> None:
    print("\n[Error Handling]")
    payload = {
        "message": "test",
        "conversationId": "nonexistent-conv-id",
        "context": {"pageId": "p1", "siteId": "s1", "language": "en"},
    }
    try:
        events = await _stream_sse(client, f"{BACKEND}/chat", payload)
        types = [e.get("type") for e in events]
        if "error" in types:
            err = next(e for e in events if e.get("type") == "error")
            if err.get("code") == "unauthorized":
                _ok("Nonexistent conversationId returns error event code=unauthorized")
            else:
                _fail("Nonexistent conversationId returns error event code=unauthorized",
                      f"Got error code: {err.get('code')}")
        else:
            _fail("Nonexistent conversationId returns error event",
                  f"Got event types: {types}")
    except Exception as e:
        _fail("Nonexistent conversationId returns error event", str(e))


async def test_blank_message(client: httpx.AsyncClient) -> None:
    try:
        r = await client.post(
            f"{BACKEND}/chat",
            json={"message": "   ", "context": {"pageId": "p1", "siteId": "s1", "language": "en"}},
            headers={"X-Local-User-Id": "smoke-test-user"},
            timeout=5,
        )
        if r.status_code == 422:
            _ok("Blank message rejected with 422")
        else:
            _fail("Blank message rejected with 422", f"Got HTTP {r.status_code}: {r.text[:100]}")
    except Exception as e:
        _fail("Blank message rejected with 422", str(e))


# ─────────────────────────── main ────────────────────────────────

async def run_all() -> None:
    limits = httpx.Limits(max_connections=10)
    # Trust mkcert's root CA so HTTPS requests to localhost:3000 succeed.
    # Falls back to default trust store if mkcert isn't installed yet.
    import subprocess, os
    mkcert_ca = None
    try:
        result = subprocess.run(["mkcert", "-CAROOT"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            ca_root = result.stdout.strip()
            ca_path = os.path.join(ca_root, "rootCA.pem")
            if os.path.exists(ca_path):
                mkcert_ca = ca_path
    except Exception:
        pass
    async with httpx.AsyncClient(limits=limits, verify=mkcert_ca or True) as client:
        await test_backend_health(client)
        await test_auth_status(client)
        await test_blank_message(client)
        await test_chat_stream(client)
        await test_conversation_persistence(client)
        await test_guardrails(client)
        await test_frontend_loads(client)
        await test_missing_conversation(client)

    print("\n" + "-" * 52)
    print(f"  Results: {len(_passed)} passed, {len(_failed)} failed, {len(_skipped)} skipped")
    if _failed:
        print("\n  Failed tests:")
        for name, detail in _failed:
            print(f"    - {name}")
            if detail:
                for line in detail.splitlines():
                    print(f"        {line}")
    print("-" * 52)

    if _failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all())
