import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const RUNTIME_CONTEXT = process.env.RUNTIME_CONTEXT ?? "iframe";

function buildHeaders(req: NextRequest): Record<string, string> | null {
  const headers: Record<string, string> = {};
  if (RUNTIME_CONTEXT === "local") {
    headers["X-Local-User-Id"] = process.env.LOCAL_USER_ID ?? "local-user";
  } else {
    const auth = req.headers.get("Authorization");
    if (!auth) return null;
    headers["Authorization"] = auth;
  }
  return headers;
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const headers = buildHeaders(req);
  if (!headers) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const upstream = await fetch(`${API_URL}/conversations/${id}`, { headers });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const headers = buildHeaders(req);
  if (!headers) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const upstream = await fetch(`${API_URL}/conversations/${id}`, {
    method: "DELETE",
    headers,
  });
  if (upstream.status === 204) return new NextResponse(null, { status: 204 });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
