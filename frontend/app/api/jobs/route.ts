import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const RUNTIME_CONTEXT = process.env.RUNTIME_CONTEXT ?? "iframe";

export async function GET(req: NextRequest) {
  const handle = req.nextUrl.searchParams.get("handle");
  if (!handle) {
    return NextResponse.json({ error: "missing handle" }, { status: 400 });
  }

  const headers: Record<string, string> = {};

  if (RUNTIME_CONTEXT === "local") {
    headers["X-Local-User-Id"] = process.env.LOCAL_USER_ID ?? "local-user";
  } else {
    const auth = req.headers.get("Authorization") ?? req.headers.get("authorization");
    if (!auth) {
      return NextResponse.json({ error: "unauthorized" }, { status: 401 });
    }
    headers["Authorization"] = auth;
  }

  try {
    const upstream = await fetch(
      `${API_URL}/jobs?handle=${encodeURIComponent(handle)}`,
      { headers }
    );
    const data = await upstream.json();
    return NextResponse.json(data, { status: upstream.status });
  } catch {
    return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
  }
}
