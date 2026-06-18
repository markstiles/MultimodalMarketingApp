import { NextRequest, NextResponse } from "next/server";

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const returnTo = searchParams.get("returnTo") ?? "/";
  const conversationId = searchParams.get("conversationId") ?? "";

  const issuer = process.env.AUTH0_ISSUER_BASE_URL ?? "";
  const clientId = process.env.AUTH0_CLIENT_ID ?? "";
  const baseUrl = process.env.AUTH0_BASE_URL ?? req.nextUrl.origin;
  const redirectUri = `${baseUrl}/api/auth/callback`;

  const state = Buffer.from(JSON.stringify({ returnTo, conversationId })).toString(
    "base64url"
  );

  const url = new URL(`${issuer}/authorize`);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", "openid profile email offline_access");
  url.searchParams.set("state", state);

  return NextResponse.redirect(url.toString());
}
