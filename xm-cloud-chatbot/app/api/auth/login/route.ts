import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { getOrCreateOAuthClient } from '@/lib/mcp/oauth-client';

// Generate PKCE code verifier and challenge
function generatePKCE() {
  // Generate a random code verifier (43-128 characters)
  const codeVerifier = crypto.randomBytes(32).toString('base64url');
  
  // Generate code challenge using S256 method
  const codeChallenge = crypto
    .createHash('sha256')
    .update(codeVerifier)
    .digest('base64url');
  
  return { codeVerifier, codeChallenge };
}

function generateStateNonce() {
  return crypto.randomBytes(16).toString('base64url');
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get('userId');
  const redirectUri = searchParams.get('redirectUri') || '/';

  if (!userId) {
    return NextResponse.json(
      { error: 'userId is required' },
      { status: 400 }
    );
  }

  // Generate PKCE values
  const { codeVerifier, codeChallenge } = generatePKCE();
  const stateNonce = generateStateNonce();

  // Build OAuth authorization URL
  const oauthAuthUrl = process.env.OAUTH_AUTHORIZATION_URL!;
  const callbackUrl =
    process.env.OAUTH_REDIRECT_URI ||
    `${process.env.NEXT_PUBLIC_BASE_URL}/api/auth/callback`;

  const oauthClient = await getOrCreateOAuthClient({
    name: 'marketer-mcp',
    oauthAuthorizationUrl: oauthAuthUrl,
    redirectUri: callbackUrl,
  });

  const authUrl = new URL(oauthAuthUrl);
  authUrl.searchParams.set('client_id', oauthClient.clientId);
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('redirect_uri', callbackUrl);
  // Use an opaque state value; store the actual payload server-side (cookie)
  authUrl.searchParams.set('state', stateNonce);
  
  // Add PKCE parameters
  authUrl.searchParams.set('code_challenge', codeChallenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');

  // Add resource parameter for Marketer MCP
  const resource =
    process.env.OAUTH_AUDIENCE ||
    'https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod';
  authUrl.searchParams.set('resource', resource);
  
  // Add scope
  const scope = process.env.OAUTH_SCOPE || 'openid profile email';
  authUrl.searchParams.set('scope', scope);

  // Store code verifier in a cookie for the callback
  const response = NextResponse.redirect(authUrl.toString());

  // Store state payload in a cookie (short-lived) to validate callback
  response.cookies.set(
    'oauth_state',
    JSON.stringify({ nonce: stateNonce, userId, redirectUri }),
    {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 600, // 10 minutes
      path: '/api/auth',
    }
  );

  response.cookies.set('pkce_code_verifier', codeVerifier, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 600, // 10 minutes
    path: '/api/auth',
  });

  return response;
}
