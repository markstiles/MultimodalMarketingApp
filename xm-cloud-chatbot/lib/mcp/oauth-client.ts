import { prisma } from '@/lib/db';

export type StoredOAuthClient = {
  issuer: string;
  clientId: string;
  clientSecret: string;
  redirectUri: string;
};

type RegistrationResponse = {
  client_id?: string;
  client_secret?: string;
  redirect_uris?: string[];
  token_endpoint_auth_method?: string;
};

function getIssuerFromAuthUrl(oauthAuthorizationUrl: string): string {
  return new URL(oauthAuthorizationUrl).origin;
}

function getRegistrationEndpoint(issuer: string): string {
  return `${issuer}/mcp/register`;
}

export async function getOrCreateOAuthClient(params: {
  name: string;
  oauthAuthorizationUrl: string;
  redirectUri: string;
}): Promise<StoredOAuthClient> {
  const issuer = getIssuerFromAuthUrl(params.oauthAuthorizationUrl);
  const useDynamicRegistration = (process.env.OAUTH_DYNAMIC_REGISTRATION ?? 'true') !== 'false';

  // If dynamic registration is disabled, fall back to env credentials.
  if (!useDynamicRegistration) {
    const envClientId = process.env.OAUTH_CLIENT_ID;
    const envClientSecret = process.env.OAUTH_CLIENT_SECRET;

    if (!envClientId || !envClientSecret) {
      throw new Error('OAuth client credentials not configured (OAUTH_CLIENT_ID / OAUTH_CLIENT_SECRET)');
    }

    return {
      issuer,
      clientId: envClientId,
      clientSecret: envClientSecret,
      redirectUri: params.redirectUri,
    };
  }

  // Dynamic client registration: persist the client so callback + refresh can reuse it.
  const existing = await prisma.oAuthClient.findUnique({
    where: { name: params.name },
  });

  if (existing && existing.issuer === issuer && existing.redirectUri === params.redirectUri) {
    return {
      issuer: existing.issuer,
      clientId: existing.clientId,
      clientSecret: existing.clientSecret,
      redirectUri: existing.redirectUri,
    };
  }

  const registrationUrl = process.env.OAUTH_REGISTRATION_URL || getRegistrationEndpoint(issuer);
  const body = {
    client_name: params.name,
    redirect_uris: [params.redirectUri],
    grant_types: ['authorization_code', 'refresh_token'],
    response_types: ['code'],
    token_endpoint_auth_method: 'client_secret_post',
  };

  const response = await fetch(registrationUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`OAuth dynamic registration failed: ${response.status} ${errorText}`);
  }

  const data = (await response.json()) as RegistrationResponse;

  if (!data.client_id || !data.client_secret) {
    throw new Error('OAuth dynamic registration response missing client_id/client_secret');
  }

  await prisma.oAuthClient.upsert({
    where: { name: params.name },
    update: {
      issuer,
      clientId: data.client_id,
      clientSecret: data.client_secret,
      redirectUri: params.redirectUri,
    },
    create: {
      name: params.name,
      issuer,
      clientId: data.client_id,
      clientSecret: data.client_secret,
      redirectUri: params.redirectUri,
    },
  });

  return {
    issuer,
    clientId: data.client_id,
    clientSecret: data.client_secret,
    redirectUri: params.redirectUri,
  };
}
