import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const RUNTIME_CONTEXT = process.env.RUNTIME_CONTEXT ?? "iframe";

export async function GET(req: NextRequest) {
  if (RUNTIME_CONTEXT === "local") {
    return NextResponse.json({
      authenticated: true,
      user: { id: "local-user", email: "dev@local" },
      expiresAt: null,
    });
  }

  const auth = req.headers.get("Authorization") ?? "";
  const upstream = await fetch(`${API_URL}/auth/status`, {
    headers: auth ? { Authorization: auth } : {},
  });
  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
