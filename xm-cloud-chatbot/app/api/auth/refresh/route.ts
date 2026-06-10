import { NextRequest, NextResponse } from 'next/server';
import { prisma } from '@/lib/db';
import { getOrCreateOAuthClient } from '@/lib/mcp/oauth-client';
import { corsHeaders, handleOptions } from '@/lib/cors';

export async function OPTIONS(req: NextRequest) {
  return handleOptions(req);
}

export async function POST(req: NextRequest) {
  try {
    const { userId } = await req.json();

    if (!userId) {
      return NextResponse.json(
        { error: 'userId is required' },
        { status: 400 }
      );
    }

    // Get current token from database
    const tokenRecord = await prisma.oAuthToken.findUnique({
      where: { userId },
    });

    if (!tokenRecord || !tokenRecord.refreshToken) {
      return NextResponse.json(
        { error: 'No refresh token available', requiresAuth: true },
        { status: 401 }
      );
    }

    // Refresh the access token
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

    const tokenResponse = await fetch(tokenUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: tokenRecord.refreshToken,
        client_id: clientId,
        client_secret: clientSecret,
      }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.text();
      console.error('Token refresh failed:', errorData);
      return NextResponse.json(
        { error: 'Failed to refresh token', requiresAuth: true },
        { status: 401 }
      );
    }

    const tokenData = await tokenResponse.json();
    const {
      access_token,
      refresh_token,
      expires_in,
      token_type = 'Bearer',
      scope,
    } = tokenData;

    // Calculate expiration time
    const expiresAt = new Date(Date.now() + expires_in * 1000);

    // Update tokens in database
    await prisma.oAuthToken.update({
      where: { userId },
      data: {
        accessToken: access_token,
        refreshToken: refresh_token || tokenRecord.refreshToken,
        expiresAt,
        tokenType: token_type,
        scope: scope || tokenRecord.scope,
      },
    });

    return NextResponse.json({
      success: true,
      expiresAt: expiresAt.toISOString(),
    });
  } catch (error) {
    console.error('Error refreshing token:', error);
    return NextResponse.json(
      { error: 'Internal server error', requiresAuth: true },
      { status: 500 }
    );
  }
}
