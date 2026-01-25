import { prisma } from '@/lib/db';
import { createWriteStream } from 'node:fs';
import { access, mkdir, readFile, unlink } from 'node:fs/promises';
import path from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { experimental_createXMCClient } from '@sitecore-marketplace-sdk/xmc';
import dotenv from 'dotenv';

// Ensure env vars are loaded
dotenv.config({ path: path.resolve(process.cwd(), '.env') });

export type AgentApiUploadAssetArgs = {
  filePath: string;
  name: string;
  itemPath: string;
  language: string;
  extension: string;
  siteName: string;

  // Optional: if the asset URL is not publicly readable, callers may provide headers
  // (e.g., Authorization or a signed-cookie header) to allow the server to fetch it.
  downloadHeaders?: Record<string, string>;

  // Optional: allow passing file content directly when a URL cannot be fetched.
  // Base64-encoded bytes of the file.
  fileContentBase64?: string;
};

export type AgentApiUpdateAssetArgs = {
  assetId: string;
  language: string;
  name?: string;
  altText?: string;
  fields?: Record<string, unknown>;
};

type ClientCredentialsTokenResponse = {
  access_token: string;
  expires_in: number;
  token_type: string;
  scope?: string;
};

let cachedClientCredentialsToken:
  | {
      token: string;
      expiresAtMs: number;
    }
  | undefined;

export function hasAgentApiCredentialsConfigured(): boolean {
  return Boolean(
    process.env.SITECORE_AGENT_API_JWT ||
    (process.env.SITECORE_AGENT_API_CLIENT_ID && process.env.SITECORE_AGENT_API_CLIENT_SECRET) ||
    (process.env.OAUTH_CLIENT_ID && process.env.OAUTH_CLIENT_SECRET && process.env.OAUTH_TOKEN_URL)
  );
}

function getAgentApiBaseUrl(): string {
  return (process.env.SITECORE_AGENT_API_BASE_URL || 'https://edge-platform.sitecorecloud.io/stream/ai-agent-api').replace(
    /\/+$/,
    ''
  );
}

export async function getClientCredentialsJwt(): Promise<string | null> {
  // 1. If a hardcoded JWT is provided (e.g. for development), use it directly.
  if (process.env.SITECORE_AGENT_API_JWT) {
    return process.env.SITECORE_AGENT_API_JWT;
  }

  // 2. Use automation credentials with standard Auth0 flow
  // Based on testing, ONLY this combination yields a valid token:
  // Client: SITECORE_AGENT_API_*
  // URL: https://auth.sitecorecloud.io/oauth/token
  // Audience: https://api.sitecorecloud.io (Standard Claims)
  
  const clientId = process.env.SITECORE_AGENT_API_CLIENT_ID;
  const clientSecret = process.env.SITECORE_AGENT_API_CLIENT_SECRET;
  
  if (!clientId || !clientSecret) {
      console.warn('[Agent API] SITECORE_AGENT_API_CLIENT_ID/SECRET not configured.');
      // Fallback or fail? If we try OAUTH creds here they likely fail with "Grant type not allowed" (403)
      return null;
  }

  const tokenUrl = 'https://auth.sitecorecloud.io/oauth/token';
  const audience = 'https://api.sitecorecloud.io'; 
  const grantType = 'client_credentials';

  console.log(`[Agent API] Requesting Token from ${tokenUrl} for audience ${audience} using Automation Client...`);

  const body = new URLSearchParams();
  body.set('client_id', clientId);
  body.set('client_secret', clientSecret);
  body.set('grant_type', grantType);
  body.set('audience', audience);

  const resp = await fetch(tokenUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      Accept: 'application/json',
    },
    body,
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`Agent API token request failed: ${resp.status} ${text}`);
  }

  const data = (await resp.json()) as ClientCredentialsTokenResponse;
  if (!data.access_token) {
    throw new Error('Agent API token response missing access_token');
  }

  // DEBUG: Decode token to verify audience
  try {
      const parts = data.access_token.split('.');
      if (parts.length === 3) {
          const payload = JSON.parse(Buffer.from(parts[1], 'base64').toString());
          console.log('[Agent API] Service Token Acquired. Claims:', { 
              iss: payload.iss, 
              aud: payload.aud 
          });
      }
  } catch (e) {
      console.warn('[Agent API] Failed to decode token claims for debug logging');
  }

  cachedClientCredentialsToken = {
    token: data.access_token,
    expiresAtMs: Date.now() + (data.expires_in ?? 0) * 1000,
  };

  return data.access_token;
}

async function getAgentApiBearerToken(userId: string): Promise<string> {
  const envJwt = process.env.SITECORE_AGENT_API_JWT;
  if (envJwt) return envJwt;

  try {
    const cc = await getClientCredentialsJwt();
    if (cc) return cc;
  } catch (err) {
    // If CC is configured but failing, surface that clearly.
    throw err;
  }

  // Do NOT fall back to the user's Marketer OAuth token by default.
  // In practice it often doesn't contain the right audience/claims for the Agent API,
  // and Sitecore may respond with confusing 404 NotFound + "Failed to extract claims from token".
  // If you truly want to allow user tokens, set SITECORE_AGENT_API_ALLOW_USER_TOKEN=true.
  const allowUserToken = (process.env.SITECORE_AGENT_API_ALLOW_USER_TOKEN ?? 'false') === 'true';
  if (allowUserToken) {
    const tokenRecord = await prisma.oAuthToken.findUnique({ where: { userId } });
    if (tokenRecord?.accessToken) return tokenRecord.accessToken;
  }

  throw new Error(
    'Agent API credentials are not configured. Set SITECORE_AGENT_API_CLIENT_ID and SITECORE_AGENT_API_CLIENT_SECRET (recommended) or SITECORE_AGENT_API_JWT.'
  );
}

function buildAgentApiAuthHint(status: number, responseText: string): string {
  const lower = responseText.toLowerCase();
  if (lower.includes('failed to extract claims from token')) {
    return `\nHint: the token used for the Agent API is not valid for this endpoint. Configure SITECORE_AGENT_API_CLIENT_ID/SITECORE_AGENT_API_CLIENT_SECRET or SITECORE_AGENT_API_JWT (do not rely on the Marketer OAuth user token).`;
  }
  if (status === 401 || status === 403) {
    return `\nHint: authentication/authorization failed. Configure SITECORE_AGENT_API_CLIENT_ID/SITECORE_AGENT_API_CLIENT_SECRET or SITECORE_AGENT_API_JWT.`;
  }
  return '';
}

function inferMimeType(extension: string, responseContentType?: string | null): string {
  if (responseContentType && responseContentType.includes('/')) return responseContentType;

  const ext = extension.replace(/^\./, '').toLowerCase();
  switch (ext) {
    case 'png':
      return 'image/png';
    case 'jpg':
    case 'jpeg':
      return 'image/jpeg';
    case 'gif':
      return 'image/gif';
    case 'webp':
      return 'image/webp';
    case 'svg':
      return 'image/svg+xml';
    case 'pdf':
      return 'application/pdf';
    case 'mp4':
      return 'video/mp4';
    default:
      return 'application/octet-stream';
  }
}

function ensureNameHasExtension(name: string, extension: string): string {
  const ext = extension.replace(/^\./, '');
  if (!ext) return name;
  const lower = name.toLowerCase();
  if (lower.endsWith(`.${ext.toLowerCase()}`)) return name;
  return `${name}.${ext}`;
}

function makeJobId(prefix = 'xm-cloud-chatbot'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getUploadDir(): string {
  return path.resolve(process.env.ASSET_UPLOAD_DIR || path.join(process.cwd(), 'uploads'));
}

function isPathInsideDir(baseDir: string, candidate: string): boolean {
  const base = path.resolve(baseDir);
  const target = path.resolve(candidate);

  // Ensure trailing separator so "C:\foo" doesn't match "C:\foobar".
  const baseWithSep = base.endsWith(path.sep) ? base : base + path.sep;

  // Windows paths should be treated case-insensitively.
  return target.toLowerCase().startsWith(baseWithSep.toLowerCase());
}

function randomHex(len = 8): string {
  return Math.random().toString(16).slice(2).padEnd(len, '0').slice(0, len);
}

function isPrivateHostname(hostname: string): boolean {
  const h = hostname.toLowerCase();
  if (h === 'localhost' || h === '127.0.0.1' || h === '::1') return true;

  // Rough IPv4 private ranges check
  const m = h.match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return false;
  const a = Number(m[1]);
  const b = Number(m[2]);
  if (a === 10) return true;
  if (a === 192 && b === 168) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  return false;
}

function sanitizeDownloadHeaders(headers?: Record<string, string>): Record<string, string> {
  if (!headers) return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(headers)) {
    if (!k) continue;
    // Avoid allowing callers to override Host/Content-Length/etc.
    const key = k.trim();
    const lower = key.toLowerCase();
    if (['host', 'content-length'].includes(lower)) continue;
    out[key] = String(v);
  }
  return out;
}

async function writeBytesToTempFile(bytes: Buffer, extension: string): Promise<string> {
  const uploadDir = getUploadDir();
  await mkdir(uploadDir, { recursive: true });
  const ext = extension.replace(/^\./, '') || 'bin';
  const tempPath = path.join(uploadDir, `upload-${Date.now()}-${randomHex(10)}.${ext}`);
  await pipeline(Readable.from(bytes), createWriteStream(tempPath));
  return tempPath;
}

async function downloadUrlToTempFile(url: string, extension: string, downloadHeaders?: Record<string, string>): Promise<string> {
  const uploadDir = getUploadDir();
  await mkdir(uploadDir, { recursive: true });

  const ext = extension.replace(/^\./, '') || 'bin';
  const tempPath = path.join(uploadDir, `download-${Date.now()}-${randomHex(10)}.${ext}`);

  const parsed = new URL(url);
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    throw new Error(`Refusing to download non-http(s) URL: ${parsed.protocol}`);
  }
  if (isPrivateHostname(parsed.hostname)) {
    throw new Error(`Refusing to download URL from private host: ${parsed.hostname}`);
  }

  const resp = await fetch(url, {
    headers: sanitizeDownloadHeaders(downloadHeaders),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    const hint =
      text.includes('PublicAccessNotPermitted') || text.includes('Public access is not permitted')
        ? `\nHint: this URL is not publicly readable (Azure "PublicAccessNotPermitted"). You need either a signed/public URL, or provide downloadHeaders, or provide fileContentBase64.`
        : '';
    throw new Error(`Failed to fetch asset from URL: ${resp.status} ${text}${hint}`);
  }

  if (!resp.body) {
    throw new Error('Failed to fetch asset from URL: response body is empty');
  }

  await pipeline(Readable.fromWeb(resp.body as any), createWriteStream(tempPath));
  return tempPath;
}

async function loadFileBytes(args: AgentApiUploadAssetArgs): Promise<{ bytes: Buffer; contentType?: string | null; filename: string }> {
  const filename = ensureNameHasExtension(args.name, args.extension);

  // Local file
  const uploadDir = getUploadDir();

  // Allow relative paths, but force them under the uploads directory.
  // Support both:
  // - "fiber.jpg" (treated as uploads/fiber.jpg)
  // - "uploads/fiber.jpg" (already rooted at uploads/)
  let candidatePath: string;
  if (path.isAbsolute(args.filePath)) {
    candidatePath = args.filePath;
  } else {
    const firstSegment = args.filePath.split(/[\\/]/).filter(Boolean)[0]?.toLowerCase();
    candidatePath =
      firstSegment === 'uploads'
        ? path.join(process.cwd(), args.filePath)
        : path.join(uploadDir, args.filePath);
  }
  const resolved = path.resolve(candidatePath);

  if (!isPathInsideDir(uploadDir, resolved)) {
    throw new Error(
      `Refusing to read local file outside uploads directory. Place the file under ${uploadDir} and pass a filePath relative to it (or an absolute path within it). Received: ${args.filePath}`
    );
  }

  try {
    await access(resolved);
  } catch {
    throw new Error(
      `Local file not found: ${resolved}\nExpected files under: ${uploadDir}\n\nThis happened because filePath ("${args.filePath}") is being treated as a LOCAL file path.\nIf you intended the server to download the image for you, pass filePath as an http(s) URL (or pass fileContentBase64 / a data: URL).\nIf the URL is private (e.g., Azure PublicAccessNotPermitted), provide a signed/public URL or pass downloadHeaders so the server can fetch it.`
    );
  }

  const buf = await readFile(resolved);
  return { bytes: buf, contentType: null, filename };
}

export async function uploadAssetViaAgentApi(userId: string, args: AgentApiUploadAssetArgs): Promise<unknown> {
  const token = await getAgentApiBearerToken(userId);
  const baseUrl = getAgentApiBaseUrl();

  // If a URL is provided, download it to a temp file under uploads/ first,
  // then upload that file and delete it afterwards.
  let tempDownloadedPath: string | null = null;
  let effectiveArgs = args;

  // If content is provided inline, write it to a temp file first.
  if (args.fileContentBase64) {
    const bytes = Buffer.from(args.fileContentBase64, 'base64');
    tempDownloadedPath = await writeBytesToTempFile(bytes, args.extension);
    effectiveArgs = { ...args, filePath: tempDownloadedPath };
  } else if (/^data:/i.test(args.filePath)) {
    const m = args.filePath.match(/^data:([^;,]+)?(;base64)?,(.*)$/i);
    if (!m || !m[3]) {
      throw new Error('Invalid data: URL provided for filePath');
    }
    const isBase64 = !!m[2];
    const payload = m[3];
    const bytes = isBase64 ? Buffer.from(payload, 'base64') : Buffer.from(decodeURIComponent(payload), 'utf8');
    tempDownloadedPath = await writeBytesToTempFile(bytes, args.extension);
    effectiveArgs = { ...args, filePath: tempDownloadedPath };
  } else if (/^https?:\/\//i.test(args.filePath)) {
    tempDownloadedPath = await downloadUrlToTempFile(args.filePath, args.extension, args.downloadHeaders);
    effectiveArgs = { ...args, filePath: tempDownloadedPath };
  }

  try {
    const { bytes, contentType, filename } = await loadFileBytes(effectiveArgs);
    const mime = inferMimeType(effectiveArgs.extension, contentType);

    const form = new FormData();
    const arrayBuffer = (bytes.buffer as ArrayBuffer).slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    form.append('file', new Blob([arrayBuffer], { type: mime }), filename);
    form.append(
      'upload_request',
      JSON.stringify({
        name: filename,
        itemPath: effectiveArgs.itemPath,
        language: effectiveArgs.language,
        extension: effectiveArgs.extension.replace(/^\./, ''),
        siteName: effectiveArgs.siteName,
      })
    );

    const resp = await fetch(`${baseUrl}/api/v1/assets/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
        'x-sc-job-id': makeJobId(),
      },
      body: form,
    });

    const text = await resp.text();
    if (!resp.ok) {
      throw new Error(`Agent API upload failed: ${resp.status} ${text}${buildAgentApiAuthHint(resp.status, text)}`);
    }

    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  } finally {
    if (tempDownloadedPath) {
      await unlink(tempDownloadedPath).catch(() => undefined);
    }
  }
}

export async function updateAssetViaAgentApi(userId: string, args: AgentApiUpdateAssetArgs): Promise<unknown> {
  const token = await getAgentApiBearerToken(userId);
  const baseUrl = getAgentApiBaseUrl();

  if (!args.assetId) {
    throw new Error('updateAssetViaAgentApi requires assetId');
  }
  if (!args.language) {
    throw new Error('updateAssetViaAgentApi requires language');
  }

  const fields: Record<string, unknown> = { ...(args.fields ?? {}) };
  if (typeof args.altText === 'string' && args.altText.trim()) {
    // In this project/environment, the correct alt field name is 'Alt'.
    if (fields.Alt === undefined) fields.Alt = args.altText;
  }

  const body = {
    fields,
    language: args.language,
    name: args.name ?? null,
    altText: args.altText ?? null,
  };

  const resp = await fetch(`${baseUrl}/api/v1/assets/${encodeURIComponent(args.assetId)}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'x-sc-job-id': makeJobId(),
    },
    body: JSON.stringify(body),
  });

  const text = await resp.text();
  if (!resp.ok) {
    throw new Error(`Agent API update_asset failed: ${resp.status} ${text}${buildAgentApiAuthHint(resp.status, text)}`);
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// Wrapper for XMC SDK Page Listing
export async function getAllPagesForSite(siteId: string, language: string, accessToken: string, environmentHost: string) {
  try {
     // Initialize the SDK Client
     // We define the API host explicitly to use the one that works with our token (xmapps-api)
     // The SDK defaults to edge-platform for 'sites', which rejects our Automation Token.
     const xmc = await experimental_createXMCClient({
        getAccessToken: async () => accessToken,
        // We leave the SDK defaults for the Agent API calls (which use edge-platform)
     });
     
     // 1. Resolve Site Name from Site ID
     console.log(`[getAllPagesForSite] resolving name for siteId: ${siteId}`);
     
     // Manual Fetch Bypass: The SDK's retrieveSite is finicky with base URLs and our specific token.
     // We know xmapps-api accepts this token and returns the name.
     const siteNameRes = await fetch(`https://xmapps-api.sitecorecloud.io/api/v1/sites/${siteId}`, {
        headers: {
            Authorization: `Bearer ${accessToken}`
        }
     });

     if (!siteNameRes.ok) {
         const txt = await siteNameRes.text();
         console.error(`[getAllPagesForSite] Name resolution failed: ${siteNameRes.status} ${txt}`);
         throw new Error(`Could not resolve site name from ID ${siteId} (Status: ${siteNameRes.status})`);
     }

     const siteData = await siteNameRes.json();
     const siteName = siteData.name;

     if (!siteName) {
         throw new Error(`Could not resolve site name from ID ${siteId} (Field missing in response)`);
     }
     console.log(`[getAllPagesForSite] Site Name: ${siteName}`);

     // 2. Fetch Pages using SDK (Agent API)

     // 2. Fetch Pages using SDK
     // This uses the SDK's built-in fetch logic
     const pagesResult = await xmc.agent.sitesGetAllPagesBySite({
        path: { siteName },
        query: { language }
     });

     const allPages = pagesResult.data || [];
     console.log(`[getAllPagesForSite] Success. Found ${allPages.length} pages via XMC SDK.`);
    
     return allPages.map((p: any) => ({
        id: p.id,
        name: p.name,
        displayName: p.displayName || p.name,
        path: p.path,
        url: p.url
     }));

  } catch (error: any) {
    console.error('Failed to list pages via XM Apps API:', error);
    throw error;
  }
}

