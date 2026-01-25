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

     // 2. Fetch Pages using Direct Fetch
     // The SDK (xmc.agent.sitesGetAllPagesBySite) fails because the API returns a raw array [{...}],
     // but the SDK likely expects { data: [...] }.
     const agentBaseUrl = getAgentApiBaseUrl();
     const pagesUrl = `${agentBaseUrl}/api/v1/sites/${siteName}/pages?language=${language}`;
     
     console.log(`[getAllPagesForSite] Fetching pages from: ${pagesUrl}`);
     
     const pagesRes = await fetch(pagesUrl, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!pagesRes.ok) {
         throw new Error(`Failed to fetch pages: ${pagesRes.status} ${await pagesRes.text()}`);
     }

     const allPages = await pagesRes.json();
     console.log(`[getAllPagesForSite] Success. Found ${allPages.length} pages via Direct Fetch.`);
    
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

export async function getComponentsOnPage(pageId: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}/components?language=${language}`;
     
     console.log(`[getComponentsOnPage] Fetching components from: ${url}`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to fetch components: ${res.status} ${await res.text()}`);
     }

     const components = await res.json();
     console.log(`[getComponentsOnPage] Success. Found ${components.length} components.`);
     
     return components; // Return raw component data
  } catch (error: any) {
    console.error('Failed to get components via XM Apps API:', error);
    throw error;
  }
}

export async function getAllowedComponents(pageId: string, placeholderName: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}/placeholders/${placeholderName}/allowed-components?language=${language}`;
     
     console.log(`[getAllowedComponents] Fetching allowed components from: ${url}`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to fetch allowed components: ${res.status} ${await res.text()}`);
     }

     const components = await res.json();
     console.log(`[getAllowedComponents] Success. Found ${components.length} allowed components.`);
     
     return components;
  } catch (error: any) {
    console.error('Failed to get allowed components via XM Apps API:', error);
    throw error;
  }
}

export async function getPage(pageId: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}?language=${language}`;
     
     console.log(`[getPage] Fetching page info from: ${url}`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to fetch page info: ${res.status} ${await res.text()}`);
     }

     const page = await res.json();
     console.log(`[getPage] Success.`);
     return page;
  } catch (error: any) {
    console.error('Failed to get page via XM Apps API:', error);
    throw error;
  }
}

export async function getPageHtml(pageId: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}/html?language=${language}`;
     
     console.log(`[getPageHtml] Fetching page HTML from: ${url}`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to fetch page HTML: ${res.status} ${await res.text()}`);
     }

     const html = await res.text();
     console.log(`[getPageHtml] Success. Length: ${html.length}`);
     return html;
  } catch (error: any) {
    console.error('Failed to get page html via XM Apps API:', error);
    throw error;
  }
}

export async function getPagePathByUrl(liveUrl: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/path-by-url?url=${encodeURIComponent(liveUrl)}`;
     
     console.log(`[getPagePathByUrl] Fetching path for url: ${liveUrl}`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to fetch path by url: ${res.status} ${await res.text()}`);
     }

     const data = await res.json();
     console.log(`[getPagePathByUrl] Success: ${data.path}`);
     return data;
  } catch (error: any) {
    console.error('Failed to get path by url via XM Apps API:', error);
    throw error;
  }
}

export async function searchSite(siteName: string, query: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/search?siteName=${encodeURIComponent(siteName)}&query=${encodeURIComponent(query)}&language=${language}`;
     
     console.log(`[searchSite] Searching site '${siteName}' for '${query}'`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to search site: ${res.status} ${await res.text()}`);
     }

     const results = await res.json();
     console.log(`[searchSite] Success. Found ${results.length} results.`);
     return results;
  } catch (error: any) {
    console.error('Failed to search site via XM Apps API:', error);
    throw error;
  }
}

export async function createPage(parentId: string, templateId: string, name: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/create`;
     
     console.log(`[createPage] Creating page '${name}' under '${parentId}'`);
     
     const res = await fetch(url, {
         method: 'POST',
         headers: {
             Authorization: `Bearer ${accessToken}`,
             'Content-Type': 'application/json'
         },
         body: JSON.stringify({
            parentId,
            templateId,
            name,
            language
         })
     });

     if (!res.ok) {
         throw new Error(`Failed to create page: ${res.status} ${await res.text()}`);
     }

     const result = await res.json();
     console.log(`[createPage] Success.`);
     return result;
  } catch (error: any) {
    console.error('Failed to create page via XM Apps API:', error);
    throw error;
  }
}

export async function listComponents(siteName: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/components?siteName=${encodeURIComponent(siteName)}`;
     
     console.log(`[listComponents] Listing components for site '${siteName}'`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         throw new Error(`Failed to list components: ${res.status} ${await res.text()}`);
     }

     const results = await res.json();
     console.log(`[listComponents] Success. Found ${results.length} components.`);
     return results;
  } catch (error: any) {
    console.error('Failed to list components via XM Apps API:', error);
    throw error;
  }
}

export async function getComponent(componentName: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/components/${encodeURIComponent(componentName)}`;
     
     console.log(`[getComponent] Getting details for component '${componentName}'`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         console.warn(`[getComponent] Failed to get component: ${res.status}`);
         return null; 
     }

     const result = await res.json();
     console.log(`[getComponent] Success.`);
     return result;
  } catch (error: any) {
    console.error('Failed to get component details via XM Apps API:', error);
    throw error;
  }
}

// --------------------------------------------------------------------------
//  Pages API / Agent API - Write Operations
// --------------------------------------------------------------------------

export async function addComponentOnPage(pageId: string, componentName: string, placeholderName: string, language: string, accessToken: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}/components`;
     
     console.log(`[addComponentOnPage] Adding '${componentName}' to '${placeholderName}' on page '${pageId}'`);
     
     const res = await fetch(url, {
         method: 'POST',
         headers: {
             Authorization: `Bearer ${accessToken}`,
             'Content-Type': 'application/json'
         },
         body: JSON.stringify({
            componentName,
            placeholderName,
            language
         })
     });

     if (!res.ok) {
         throw new Error(`Failed to add component: ${res.status} ${await res.text()}`);
     }

     const result = await res.json();
     console.log(`[addComponentOnPage] Success.`);
     return result;
  } catch (error: any) {
    console.error('Failed to add component via XM Apps API:', error);
    throw error;
  }
}

export async function createContentItem(params: { name: string; templateId: string; parentId: string; language: string }, accessToken: string) {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/content/create`;
        
        console.log(`[createContentItem] Creating content item '${params.name}' under '${params.parentId}'`);
        
        const res = await fetch(url, {
            method: 'POST',
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(params)
        });

        if (!res.ok) {
            throw new Error(`Failed to create content item: ${res.status} ${await res.text()}`);
        }

        const result = await res.json();
        console.log(`[createContentItem] Success.`);
        return result;
    } catch (error: any) {
        console.error('Failed to create content item via XM Apps API:', error);
        throw error;
    }
}

export async function updateContent(params: { id: string; language: string; fields: Record<string, unknown> }, accessToken: string) {
     try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/content/${params.id}`;
        
        console.log(`[updateContent] Updating content item '${params.id}'`);
        
        const res = await fetch(url, {
            method: 'PUT',
            headers: {
                Authorization: `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                language: params.language, // API expects this at root
                // The API shape is slightly fluid, but typically PUT /content/{id} expects fields/language/version
                fields: params.fields
            })
        });

        if (!res.ok) {
            throw new Error(`Failed to update content item: ${res.status} ${await res.text()}`);
        }

        const result = await res.json();
        console.log(`[updateContent] Success.`);
        return result;
    } catch (error: any) {
        console.error('Failed to update content item via XM Apps API:', error);
        throw error;
    }
}

export async function deleteContent(itemId: string, accessToken: string) {
     try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/content/${itemId}`;
        
        console.log(`[deleteContent] Deleting content item '${itemId}'`);
        
        const res = await fetch(url, {
            method: 'DELETE',
            headers: {
                Authorization: `Bearer ${accessToken}`
            }
        });

        if (!res.ok) {
            throw new Error(`Failed to delete content item: ${res.status} ${await res.text()}`);
        }

        const result = await res.json();
        console.log(`[deleteContent] Success.`);
        return result;
    } catch (error: any) {
        console.error('Failed to delete content item via XM Apps API:', error);
        throw error;
    }
}

export async function getSitesList(accessToken: string) {
    try {
       const agentBaseUrl = getAgentApiBaseUrl();
       const url = `${agentBaseUrl}/api/v1/sites`;
       
       console.log(`[getSitesList] Listing all sites`);
       
       const res = await fetch(url, {
           headers: {
               Authorization: `Bearer ${accessToken}`
           }
       });
  
       if (!res.ok) {
           throw new Error(`Failed to list sites: ${res.status} ${await res.text()}`);
       }
  
       const data = await res.json();
       console.log(`[getSitesList] Success. Found ${data.length} sites.`);
       return data;
    } catch (error: any) {
      console.error('Failed to list sites via XM Apps API:', error);
      throw error;
    }
}

// --- New SDK Wrappers for Site Collections, Favorites, Languages, Aggregation, Jobs ---

export async function listSiteCollections(accessToken: string) {
  const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
  // @ts-ignore - SDK types might not be perfectly inferred
  return await xmc.sites.listCollections({});
}

export async function getFavoriteSites(accessToken: string) {
  const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
  // @ts-ignore
  return await xmc.sites.getFavoriteSites({});
}

export async function listLanguages(accessToken: string) {
    // client.sites.listLanguages
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.listLanguages({});
}

export async function aggregatePageData(siteId: string, pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.aggregatePageData({ siteId, pageId, language });
}

export async function listJobs(accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.listJobs({});
}

// ==========================================
// COMPREHENSIVE SDK WRAPPERS
// ==========================================

// --- Agent API Additional Wrappers ---

export async function getAssetInformation(assetId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.assetsGetAssetInformation({ assetId, language });
}

export async function searchAssets(query: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.assetsSearchAssets({ query, language });
}

// NOTE: assetsUploadAsset and assetsUpdateAsset are handled by custom functions at top of file, 
// ensuring we use the correct FormData logic.

export async function createComponentDatasource(name: string, templateId: string, locationId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.componentsCreateComponentDatasource({ name, templateId, locationId, language });
}

export async function searchComponentDatasources(query: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.componentsSearchComponentDatasources({ query, language });
}

export async function listAvailableInsertOptions(itemId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.contentListAvailableInsertoptions({ itemId, language });
}

export async function addLanguageToPage(pageId: string, language: string, version: number, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.pagesAddLanguageToPage({ pageId, language, version });
}

export async function getPagePreviewUrl(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.pagesGetPagePreviewUrl({ pageId, language });
}

export async function getPageScreenshot(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.pagesGetPageScreenshot({ pageId, language });
}

export async function setComponentDatasource(pageId: string, componentId: string, datasourceId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.pagesSetComponentDatasource({ pageId, componentId, datasourceId, language });
}

export async function createPersonalizationVersion(pageId: string, conditionId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.personalizationCreatePersonalizationVersion({ pageId, conditionId, language });
}

export async function getPersonalizationVersionsByPage(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.personalizationGetPersonalizationVersionsByPage({ pageId, language });
}

export async function getSiteDetails(siteName: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.sitesGetSiteDetails({ siteName });
}

// --- Pages API Additional Wrappers ---

export async function duplicatePage(pageId: string, newName: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.duplicatePage({ pageId, newName, language });
}

export async function renamePage(pageId: string, newName: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.renamePage({ pageId, name: newName, language }); // Note property key might be 'name' based on common patterns
}

export async function addPageVersion(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.addPageVersion({ pageId, language });
}

// --- Sites API Additional Wrappers ---

export async function createSite(name: string, templateId: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.createSite({ name, templateId });
}

export async function deleteSite(siteId: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.deleteSite({ siteId });
}

export async function listPageChildren(itemId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.listPageChildren({ itemId, language });
}


// --- Comprehensive Site Management Wrappers ---

export async function getFavoriteSiteTemplates(accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.getFavoriteSiteTemplates({});
}

export async function listSiteTemplates(accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.listSiteTemplates({});
}

export async function getRenderingHosts(accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.getRenderingHosts({});
}

export async function createHost(name: string, hostName: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.createHost({ name, hostName });
}

export async function createCollection(name: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.createCollection({ name });
}

export async function deleteCollection(collectionId: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.deleteCollection({ collectionId });
}

export async function createLanguage(name: string, code: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.createLanguage({ name, code });
}

export async function deleteLanguage(language: string, accessToken: string) {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.sites.deleteLanguage({ language });
}

// --- Personalization Wrappers ---

export async function getConditionTemplates(accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.personalizationGetConditionTemplates({ language });
}

export async function getConditionTemplateById(templateId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.personalizationGetConditionTemplateById({ templateId, language });
}

// --- Page Service Wrappers ---

export async function retrievePageVersions(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.retrievePageVersions({ pageId, language });
}

export async function getLivePageState(pageId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.getLivePageState({ pageId, language });
}

export async function saveLayout(pageId: string, layout: any, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.pages.saveLayout({ pageId, layout, language });
}

export async function getPageTemplateById(templateId: string, accessToken: string, language: string = 'en') {
    const xmc = await experimental_createXMCClient({ getAccessToken: async () => accessToken });
    // @ts-ignore
    return await xmc.agent.pagesGetPageTemplateById({ templateId, language });
}








