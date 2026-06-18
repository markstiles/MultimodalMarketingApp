import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const RUNTIME_CONTEXT = process.env.RUNTIME_CONTEXT ?? "iframe";

export async function POST(req: NextRequest) {
  const body = await req.text();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (RUNTIME_CONTEXT === "local") {
    headers["X-Local-User-Id"] = process.env.LOCAL_USER_ID ?? "local-user";
  } else {
    const auth = req.headers.get("Authorization") ?? req.headers.get("authorization");
    if (!auth) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
    headers["Authorization"] = auth;
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_URL}/chat`, { method: "POST", headers, body });
  } catch (err) {
    return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
  }

  if (!upstream.ok) {
    const text = await upstream.text();
    return new NextResponse(text, { status: upstream.status });
  }

  // Pipe the SSE stream explicitly — passing upstream.body directly to
  // NextResponse can silently drop data in Next.js App Router.
  const upstreamBody = upstream.body!;
  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstreamBody.getReader();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          controller.enqueue(value);
        }
      } catch {
        // upstream closed or errored — let the browser handle it
      } finally {
        controller.close();
      }
    },
  });

  return new NextResponse(stream, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
