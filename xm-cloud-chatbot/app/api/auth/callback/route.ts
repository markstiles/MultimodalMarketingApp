import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { getOrCreateOAuthClient } from '@/lib/mcp/oauth-client';

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const code = searchParams.get('code');
  const stateParam = searchParams.get('state');
  const error = searchParams.get('error');
  const errorDescription = searchParams.get('error_description');

  // Check for OAuth errors from authorization server
  if (error) {
    console.error('OAuth authorization error:', { error, errorDescription });
    return NextResponse.json(
      { 
        error: `Authorization failed: ${error}`,
        description: errorDescription 
      },
      { status: 400 }
    );
  }

  if (!code || !stateParam) {
    return NextResponse.json(
      { error: 'Missing authorization code or state' },
      { status: 400 }
    );
  }

  // Validate opaque state using cookie payload
  const stateCookie = req.cookies.get('oauth_state')?.value;
  if (!stateCookie) {
    return NextResponse.json(
      { error: 'Missing oauth_state cookie. Please restart the login flow.' },
      { status: 400 }
    );
  }

  let state: { nonce: string; userId: string; redirectUri: string };
  try {
    state = JSON.parse(stateCookie);
  } catch {
    return NextResponse.json(
      { error: 'Invalid oauth_state cookie. Please restart the login flow.' },
      { status: 400 }
    );
  }

  if (!state?.nonce || state.nonce !== stateParam) {
    return NextResponse.json(
      { error: 'State verification failed. Please restart the login flow.' },
      { status: 400 }
    );
  }

  // Check if we already have a valid token for this user to avoid duplicate exchanges
  try {
    const existingToken = await prisma.oAuthToken.findUnique({
      where: { userId: state.userId },
    });
    
    if (existingToken && existingToken.expiresAt > new Date()) {
      // If token is opaque (not JWT), we can't validate iss/aud here.
      // Treat it as valid and reuse it to avoid forcing re-auth loops.
      if (!existingToken.accessToken.includes('.')) {
        console.log('User already has valid opaque MCP token, redirecting...');
        const redirectUrl = new URL(state.redirectUri, process.env.NEXT_PUBLIC_BASE_URL!);
        redirectUrl.searchParams.set('auth_success', 'true');
        return NextResponse.redirect(redirectUrl.toString());
      }

      // Validate issuer/resource so we don't reuse a token from a different auth server.
      const expectedIssuer = process.env.OAUTH_AUTHORIZATION_URL
        ? new URL(process.env.OAUTH_AUTHORIZATION_URL).origin
        : 'https://edge-platform.sitecorecloud.io';
      const expectedResource =
        process.env.OAUTH_AUDIENCE ||
        process.env.MARKETER_MCP_URL ||
        'https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod';

      try {
        const base64Url = existingToken.accessToken.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(
          Buffer.from(base64, 'base64')
            .toString()
            .split('')
            .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
            .join('')
        );
        const payload = JSON.parse(jsonPayload);

        const issOk = payload?.iss === expectedIssuer;
        const aud = payload?.aud;
        const audOk =
          aud === expectedResource ||
          (Array.isArray(aud) && aud.includes(expectedResource));

        if (issOk && audOk) {
          console.log('User already has valid MCP token, redirecting...');
          const redirectUrl = new URL(state.redirectUri, process.env.NEXT_PUBLIC_BASE_URL!);
          redirectUrl.searchParams.set('auth_success', 'true');
          
          // Return HTML that posts a message to the opener (popup pattern)
          return new NextResponse(
            `<html>
              <body>
                <script>
                  if (window.opener) {
                    window.opener.postMessage({ type: 'AUTH_SUCCESS', userId: '${state.userId}' }, '*');
                    window.close();
                  } else {
                    window.location.href = '${redirectUrl.toString()}';
                  }
                </script>
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif;">
                  <h2>Authentication Successful</h2>
                  <p>You can close this window now.</p>
                </div>
              </body>
            </html>`,
            {
              headers: { 'Content-Type': 'text/html' },
            }
          );
        }

        console.log('Existing token does not match expected issuer/resource; re-authenticating.');
        await prisma.oAuthToken.delete({ where: { userId: state.userId } }).catch(() => undefined);
      } catch {
        await prisma.oAuthToken.delete({ where: { userId: state.userId } }).catch(() => undefined);
      }
    }
  } catch (err) {
    console.warn('Could not check existing token:', err);
  }

  try {
    // Get code verifier from cookie for PKCE
    const codeVerifier = req.cookies.get('pkce_code_verifier')?.value;
    
    if (!codeVerifier) {
      console.error('PKCE code verifier not found in cookies');
      return NextResponse.json(
        { error: 'PKCE code verifier not found. Please restart the login flow.' },
        { status: 400 }
      );
    }

    // Exchange authorization code for tokens
    const tokenUrl = process.env.OAUTH_TOKEN_URL!;
    const callbackUrl =
      process.env.OAUTH_REDIRECT_URI ||
      `${process.env.NEXT_PUBLIC_BASE_URL}/api/auth/callback`;

    const oauthClient = await getOrCreateOAuthClient({
      name: 'marketer-mcp',
      oauthAuthorizationUrl: process.env.OAUTH_AUTHORIZATION_URL!,
      redirectUri: callbackUrl,
    });

    const clientId = oauthClient.clientId;
    const clientSecret = oauthClient.clientSecret;

    console.log('Token exchange request:', {
      tokenUrl,
      clientId: clientId.substring(0, 10) + '...',
      callbackUrl,
      code: code.substring(0, 10) + '...',
      hasPKCE: !!codeVerifier,
      timestamp: new Date().toISOString(),
    });

    // Send only required fields for authorization_code + PKCE
    const tokenResponse = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        redirect_uri: callbackUrl,
        client_id: clientId,
        client_secret: clientSecret,
        code_verifier: codeVerifier, // PKCE code verifier
      }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error('Token exchange failed with body credentials:', {
        status: tokenResponse.status,
        statusText: tokenResponse.statusText,
        error: errorData,
      });
      
      // Try again with Basic Auth (some OAuth servers prefer this)
      console.log('Retrying with Basic Auth...');
      const basicAuthResponse = await fetch(tokenUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
          'Authorization': `Basic ${Buffer.from(`${clientId}:${clientSecret}`).toString('base64')}`,
        },
        body: new URLSearchParams({
          grant_type: 'authorization_code',
          code,
          redirect_uri: callbackUrl,
          code_verifier: codeVerifier, // PKCE code verifier
        }),
      });
      
      if (!basicAuthResponse.ok) {
        const basicErrorData = await basicAuthResponse.text();
        console.error('Token exchange also failed with Basic Auth:', {
          status: basicAuthResponse.status,
          statusText: basicAuthResponse.statusText,
          error: basicErrorData,
        });
        return NextResponse.json(
          { 
            error: 'Failed to exchange authorization code',
            details: basicErrorData,
            status: basicAuthResponse.status,
            hint: 'Both body credentials and Basic Auth failed. Check client_id, client_secret, and redirect_uri.',
          },
          { status: 500 }
        );
      }
      
      // Basic Auth worked, continue with that response
      const tokenData = await basicAuthResponse.json();
      console.log('Token response received (via Basic Auth):', {
        hasAccessToken: !!tokenData.access_token,
        hasRefreshToken: !!tokenData.refresh_token,
        expiresIn: tokenData.expires_in,
        tokenType: tokenData.token_type,
      });
      
      return await processTokenResponse(tokenData, state);
    }
    
    // Body credentials worked
    const tokenData = await tokenResponse.json();
    console.log('Token response received (via body credentials):', {
      hasAccessToken: !!tokenData.access_token,
      hasRefreshToken: !!tokenData.refresh_token,
      expiresIn: tokenData.expires_in,
      tokenType: tokenData.token_type,
    });
    
    return await processTokenResponse(tokenData, state);
  } catch (error) {
    console.error('Error in OAuth callback:', error);
    return NextResponse.json(
      { error: 'Internal server error during token exchange' },
      { status: 500 }
    );
  }
}

async function processTokenResponse(tokenData: any, state: { userId: string; redirectUri: string }) {
  const {
    access_token,
    refresh_token,
    expires_in,
    token_type = 'Bearer',
    scope,
  } = tokenData;

  if (!access_token) {
    console.error('No access token in response:', tokenData);
    return NextResponse.json(
      { error: 'No access token received from OAuth server' },
      { status: 500 }
    );
  }

  // Calculate expiration time
  const expiresAt = new Date(Date.now() + (expires_in || 3600) * 1000);

  // Debug: verify token issuer/audience quickly
  try {
    const parts = String(access_token).split('.');
    if (parts.length < 2) {
      console.log('MCP access_token is not a JWT (opaque); skipping claim decode.');
    } else {
      // Prefer base64url decoding directly.
      let payloadJson: string;
      try {
        payloadJson = Buffer.from(parts[1], 'base64url').toString('utf8');
      } catch {
        // Fallback for older runtimes
        const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        payloadJson = Buffer.from(base64, 'base64').toString('utf8');
      }

      const payload = JSON.parse(payloadJson);
      console.log('MCP token claims:', {
        iss: payload.iss,
        aud: payload.aud,
        resource: payload.resource,
        scope: payload.scope,
      });
    }
  } catch (err) {
    console.warn('Could not decode MCP access token:', err);
  }

  // Store tokens in database
  await prisma.oAuthToken.upsert({
    where: { userId: state.userId },
    update: {
      accessToken: access_token,
      refreshToken: refresh_token || null,
      expiresAt,
      tokenType: token_type,
      scope: scope || null,
    },
    create: {
      userId: state.userId,
      accessToken: access_token,
      refreshToken: refresh_token || null,
      expiresAt,
      tokenType: token_type,
      scope: scope || null,
    },
  });

  // Redirect back to the app (using Popup Pattern)
  const redirectUrl = new URL(state.redirectUri, process.env.NEXT_PUBLIC_BASE_URL!);
  redirectUrl.searchParams.set('auth_success', 'true');
  
  const response = new NextResponse(
    `<html>
      <body>
        <script>
          if (window.opener) {
            window.opener.postMessage({ type: 'AUTH_SUCCESS', userId: '${state.userId}' }, '*');
            window.close();
          } else {
            window.location.href = '${redirectUrl.toString()}';
          }
        </script>
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif;">
          <h2>Authentication Successful</h2>
          <p>You can close this window now.</p>
        </div>
      </body>
    </html>`,
    {
      headers: { 'Content-Type': 'text/html' },
    }
  );
  
  // Clear the PKCE code verifier cookie
  response.cookies.delete('pkce_code_verifier');
  response.cookies.delete('oauth_state');
  
  return response;
}
