import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const refreshToken = req.cookies.get("refresh_token")?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const issuer = process.env.AUTH0_ISSUER_BASE_URL ?? "";
  const clientId = process.env.AUTH0_CLIENT_ID ?? "";
  const clientSecret = process.env.AUTH0_CLIENT_SECRET ?? "";

  const tokenRes = await fetch(`${issuer}/oauth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: refreshToken,
    }),
  });

  if (!tokenRes.ok) {
    const res = NextResponse.json({ error: "unauthorized" }, { status: 401 });
    res.cookies.delete("session_token");
    res.cookies.delete("session_expires");
    res.cookies.delete("refresh_token");
    return res;
  }

  const tokens = await tokenRes.json();
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000).toISOString();

  const res = NextResponse.json({ expiresAt });
  res.cookies.set("session_token", tokens.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "none",
    path: "/",
    maxAge: tokens.expires_in,
  });
  res.cookies.set("session_expires", expiresAt, {
    httpOnly: true,
    secure: true,
    sameSite: "none",
    path: "/",
    maxAge: tokens.expires_in,
  });

  return res;
}
