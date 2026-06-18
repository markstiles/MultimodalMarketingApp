import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const code = searchParams.get("code") ?? "";
  const rawState = searchParams.get("state") ?? "";

  let returnTo = "/";
  let conversationId = "";
  try {
    const decoded = JSON.parse(Buffer.from(rawState, "base64url").toString());
    returnTo = decoded.returnTo ?? "/";
    conversationId = decoded.conversationId ?? "";
  } catch {}

  const issuer = process.env.AUTH0_ISSUER_BASE_URL ?? "";
  const clientId = process.env.AUTH0_CLIENT_ID ?? "";
  const clientSecret = process.env.AUTH0_CLIENT_SECRET ?? "";
  const baseUrl = process.env.AUTH0_BASE_URL ?? req.nextUrl.origin;
  const redirectUri = `${baseUrl}/api/auth/callback`;

  const tokenRes = await fetch(`${issuer}/oauth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      client_secret: clientSecret,
      code,
      redirect_uri: redirectUri,
    }),
  });

  if (!tokenRes.ok) {
    return NextResponse.redirect(new URL("/api/auth/login", req.url));
  }

  const tokens = await tokenRes.json();
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000).toISOString();

  const redirectTarget = new URL(returnTo, baseUrl);
  if (conversationId) {
    redirectTarget.searchParams.set("conversationId", conversationId);
  }

  const response = NextResponse.redirect(redirectTarget.toString());
  response.cookies.set("session_token", tokens.access_token, {
    httpOnly: true,
    secure: true,
    sameSite: "none",
    path: "/",
    maxAge: tokens.expires_in,
  });
  response.cookies.set("session_expires", expiresAt, {
    httpOnly: true,
    secure: true,
    sameSite: "none",
    path: "/",
    maxAge: tokens.expires_in,
  });

  return response;
}
