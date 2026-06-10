import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { getOrCreateOAuthClient } from '@/lib/mcp/oauth-client';
import { corsHeaders, handleOptions } from '@/lib/cors';

export async function OPTIONS(req: NextRequest) {
  return handleOptions(req);
}

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
  const origin = req.headers.get('origin');

  console.log('[Auth Login] Request received. UserId:', userId);
  console.log('[Auth Login] Origin:', origin);

  if (!userId) {
    console.error('[Auth Login] User ID missing');
    return NextResponse.json(
      { error: 'userId is required' },
      { status: 400, headers: corsHeaders(origin) }
    );
  }

  // Generate PKCE values
  const { codeVerifier, codeChallenge } = generatePKCE();
  const stateNonce = generateStateNonce();

  // Build OAuth authorization URL
  const oauthAuthUrl = process.env.OAUTH_AUTHORIZATION_URL!;
  const callbackUrl =
    process.env.OAUTH_REDIRECT_URI ||
    `${(process.env.NEXT_PUBLIC_BASE_URL || 'https://localhost:3001').replace('3000', '3001')}/api/auth/callback`;

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

  console.log('[Auth Login] Final Auth URL:', authUrl.toString());

  // Store code verifier in a cookie for the callback
  const response = NextResponse.json({ url: authUrl.toString() }, { headers: corsHeaders(origin) });

  // Determine cookie settings based on environment AND origin
  // If we are on HTTPS localhost we can use Secure
  // local-ssl-proxy runs on 3001, so redirects to 3001 are considered secure
  const isHttps = origin?.startsWith('https:') || redirectUri?.startsWith('https:') || process.env.NODE_ENV === 'production';
  const secureCookie = isHttps; 
  const sameSiteValue = isHttps ? 'none' : 'lax'; // 'none' requires Secure

  console.log(`[Auth Login] Cookie Settings -> Secure: ${secureCookie}, SameSite: ${sameSiteValue}`);

  // Store state payload in a cookie (short-lived) to validate callback
  response.cookies.set(
    'oauth_state',
    JSON.stringify({ nonce: stateNonce, userId, redirectUri }),
    {
      httpOnly: true,
      secure: secureCookie,
      sameSite: sameSiteValue,
      maxAge: 600, // 10 minutes
      path: '/api/auth',
    }
  );

  response.cookies.set('pkce_code_verifier', codeVerifier, {
    httpOnly: true,
    secure: secureCookie,
    sameSite: sameSiteValue,
    maxAge: 600, // 10 minutes
    path: '/api/auth',
  });

  return response;
}
