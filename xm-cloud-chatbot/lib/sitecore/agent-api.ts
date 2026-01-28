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

// FIX: Force the XMC SDK to use the configured Agent API Base URL.
// The default SDK URL often fails in specific environments, whereas the Agent API URL (used by manual fetches) is reliable.
// We sync them here to ensure library functions use the "good" URL.
if (!process.env.EDGE_PLATFORM_PROXY_URL) {
  const agentBase = process.env.SITECORE_AGENT_API_BASE_URL || 'https://edge-platform.sitecorecloud.io/stream/ai-agent-api';
  process.env.EDGE_PLATFORM_PROXY_URL = agentBase.replace(/\/+$/, '');
  console.log(`[Agent API] Overriding SDK EDGE_PLATFORM_PROXY_URL to: ${process.env.EDGE_PLATFORM_PROXY_URL}`);
}

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
  const audience = process.env.SITECORE_AUTH_AUDIENCE || 'https://api.sitecorecloud.io';
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
     const agentBaseUrl = getAgentApiBaseUrl(); 
     
     // 1. Resolve Site Name from Site ID
     console.log(`[getAllPagesForSite] resolving name for siteId: ${siteId}`);
     
     const siteDetailsUrl = `${agentBaseUrl}/api/v1/sites/${siteId}`;
     const siteDetailRes = await fetch(siteDetailsUrl, {
         headers: { Authorization: `Bearer ${accessToken}` }
     });

     let siteName: string | undefined;

     if (siteDetailRes.ok) {
         const siteDetailResponse = await siteDetailRes.json();
         console.log(`[getAllPagesForSite] sitesGetSiteDetails response:`, JSON.stringify(siteDetailResponse, null, 2));
         siteName = siteDetailResponse.name || siteDetailResponse.data?.name;
     } else {
         console.warn(`[getAllPagesForSite] Agent API failed (${siteDetailRes.status}). Falling back to list iteration.`);
         // Fallback: Use getSitesList to find the site by ID
         try {
             const allSites = await getSitesList(accessToken);
             const match = allSites.find((s: any) => s.id === siteId);
             if (match) {
                 siteName = match.name;
                 console.log(`[getAllPagesForSite] Resolved name via getSitesList: ${siteName}`);
             }
         } catch (e) {
             console.warn(`[getAllPagesForSite] Fallback list lookup failed:`, e);
         }
     }

     if (!siteName) {
         throw new Error(`Could not resolve site name from ID ${siteId}`);
     }
     console.log(`[getAllPagesForSite] Site Name: ${siteName}`);

     // 2. Fetch Pages
     console.log(`[getAllPagesForSite] Fetching pages for site: ${siteName}`);
     
     const pagesUrl = `${agentBaseUrl}/api/v1/sites/${encodeURIComponent(siteName)}/pages?language=${language}`;
     const responseRes = await fetch(pagesUrl, {
         headers: { Authorization: `Bearer ${accessToken}` }
     });

     let response;
     if (!responseRes.ok) {
        console.warn(`[getAllPagesForSite] Agent API failed (${responseRes.status}). Falling back to xmapps-api.`);
        const fbUrl = `https://xmapps-api.sitecorecloud.io/api/v1/sites/${encodeURIComponent(siteName)}/pages?language=${language}`;
        const fbRes = await fetch(fbUrl, {
             headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!fbRes.ok) {
             throw new Error(`Failed to list pages via both Agent API and XM Apps API: ${fbRes.status} ${await fbRes.text()}`);
        }
        response = await fbRes.json();
     } else {
        response = await responseRes.json();
     }

     let allPages: any[] = [];
     if (Array.isArray(response)) {
         allPages = response;
     } else if (response && (response as any).data && Array.isArray((response as any).data)) {
         allPages = (response as any).data;
     }
     console.log(`[getAllPagesForSite] Success. Found ${allPages.length} pages.`);
    
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
       console.log(`[getComponentsOnPage] Fetching components for page: ${pageId}`);
       
       const url = `${agentBaseUrl}/api/v1/pages/${pageId}/components?language=${language}`;
       const res = await fetch(url, {
           headers: { Authorization: `Bearer ${accessToken}` }
       });

       let response;

       if (!res.ok) {
            const errorText = await res.text();
            console.warn(`[getComponentsOnPage] Agent API failed (${res.status}): ${errorText}`);

            // Fallback to xmapps-api if Agent API rejects the token
            if (res.status === 404 || res.status === 401 || res.status === 403) {
                 console.log('[getComponentsOnPage] Attempting fallback to xmapps-api...');
                 const fbUrl = `https://xmapps-api.sitecorecloud.io/api/v1/pages/${pageId}/components?language=${language}`;
                 const fbRes = await fetch(fbUrl, {
                     headers: { Authorization: `Bearer ${accessToken}` }
                 });

                 if (fbRes.ok) {
                     response = await fbRes.json();
                     console.log(`[getComponentsOnPage] Fallback success.`);
                 } else {
                     console.warn(`[getComponentsOnPage] Fallback failed: ${fbRes.status} ${await fbRes.text()}`);
                     throw new Error(`Failed to get components on page: ${res.status} ${errorText}`);
                 }
            } else {
                throw new Error(`Failed to get components on page: ${res.status} ${errorText}`);
            }
       } else {
           response = await res.json();
       }

       let components: any[] = [];
       if (Array.isArray(response)) {
           components = response;
       } else if (response && (response as any).components && Array.isArray((response as any).components)) {
           components = (response as any).components;
       } else if (response && (response as any).data && Array.isArray((response as any).data)) {
           components = (response as any).data;
       }

       console.log(`[getComponentsOnPage] Success. Found ${components.length} components.`);
       return components; // Return raw component data
    } catch (error: any) {
       console.error('Failed to get components via SDK:', error);
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
         const errorText = await res.text();
         console.warn(`[getAllowedComponents] Agent API failed (${res.status}): ${errorText}`);

         // Fallback to xmapps-api if Agent API rejects the token (Claims mismatch/404/401)
         if (res.status === 404 || res.status === 401 || res.status === 403) {
             console.log('[getAllowedComponents] Attempting fallback to xmapps-api...');
             const fbUrl = `https://xmapps-api.sitecorecloud.io/api/v1/pages/${pageId}/placeholders/${placeholderName}/allowed-components?language=${language}`;
             
             const fbRes = await fetch(fbUrl, {
                 headers: { Authorization: `Bearer ${accessToken}` }
             });
             
             if (fbRes.ok) {
                 const fbData = await fbRes.json();
                 console.log(`[getAllowedComponents] Fallback success. Found ${fbData.length} allowed components.`);
                 return fbData;
             } else {
                 console.warn(`[getAllowedComponents] Fallback failed: ${fbRes.status} ${await fbRes.text()}`);
             }
         }
         
         throw new Error(`Failed to fetch allowed components: ${res.status} ${errorText}`);
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
     const url = `${agentBaseUrl}/api/v1/components?site_name=${encodeURIComponent(siteName)}`;
     
     console.log(`[listComponents] Listing components for site '${siteName}'`);
     
     const res = await fetch(url, {
         headers: {
             Authorization: `Bearer ${accessToken}`
         }
     });

     if (!res.ok) {
         const errorText = await res.text();
         console.warn(`[listComponents] Agent API failed (${res.status}): ${errorText}`);

         // Fallback to xmapps-api
         if (res.status === 404 || res.status === 401 || res.status === 403) {
             console.log('[listComponents] Attempting fallback to xmapps-api...');
             // Try standard query param
             const fbUrl = `https://xmapps-api.sitecorecloud.io/api/v1/components?site_name=${encodeURIComponent(siteName)}`;
             const fbRes = await fetch(fbUrl, { headers: { Authorization: `Bearer ${accessToken}` } });
             
             if (fbRes.ok) {
                 const fbData = await fbRes.json();
                 console.log(`[listComponents] Fallback success.`);
                 return fbData;
             } else {
                 console.warn(`[listComponents] Fallback failed: ${fbRes.status}. Retrying with siteName param...`);
                 // Retry with camelCase just in case
                 const fbUrl2 = `https://xmapps-api.sitecorecloud.io/api/v1/components?siteName=${encodeURIComponent(siteName)}`;
                 const fbRes2 = await fetch(fbUrl2, { headers: { Authorization: `Bearer ${accessToken}` } });
                 if (fbRes2.ok) {
                     const fbData2 = await fbRes2.json();
                     console.log(`[listComponents] Fallback (siteName) success.`);
                     return fbData2;
                 }
             }
         }

         throw new Error(`Failed to list components: ${res.status} ${errorText}`);
     }

     const results = await res.json();
     
     // DEBUG: Log keys to understand structure
     if (results && typeof results === 'object') {
         console.log(`[listComponents] Response keys: ${Object.keys(results).join(', ')}`);
         if ((results as any).components) {
             console.log(`[listComponents] components type: ${typeof (results as any).components}, isArray: ${Array.isArray((results as any).components)}`);
         }
     }

     let count = 'unknown';
     if (Array.isArray(results)) count = results.length.toString();
     else if (results.items && Array.isArray(results.items)) count = results.items.length.toString();
     else if (results.data && Array.isArray(results.data)) count = results.data.length.toString();
     else if (results.components && Array.isArray(results.components)) count = results.components.length.toString();
     // Handle case where components is a map
     else if (results.components && typeof results.components === 'object') count = Object.keys(results.components).length.toString();

     console.log(`[listComponents] Success. Found ${count} components.`);
     return results;
  } catch (error: any) {
    console.error('Failed to list components via XM Apps API:', error);
    throw error;
  }
}


const GUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const isSystemId = (id: string) => GUID_REGEX.test(id);

export async function getComponent(componentName: string, accessToken: string, siteName?: string, pageId?: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     
     let targetId = componentName;
     let foundDetails = null;

     // 1. Attempt Resolution: Translate Name -> ID if possible
     if (siteName) {
         try {
             // Fetch all components for the site to resolve the name
             const listData = await listComponents(siteName, accessToken);
             let items: any[] = [];
             
             // Normalize list structure (handles Arrays, Objects, embedded 'items'/'data'/'components')
             if (Array.isArray(listData)) items = listData;
             else if (listData && Array.isArray((listData as any).items)) items = (listData as any).items;
             else if (listData && Array.isArray((listData as any).data)) items = (listData as any).data;
             else if (listData && Array.isArray((listData as any).components)) items = (listData as any).components;
             else if (listData && (listData as any).components && typeof (listData as any).components === 'object') {
                 // Handle object map { "CompName": { ... } }
                 items = Object.entries((listData as any).components).map(([key, value]: [string, any]) => {
                     // The value MUST be an object to be useful. 
                     if (value && typeof value === 'object') {
                         return { 
                            ...value, 
                            // Ensure name exists
                            name: value.name || value.Name || key, 
                            // Ensure ID exists (map 'itemId', 'id', or maybe the key itself if the values are sparse?)
                            id: value.id || value.itemId || value.Id
                         }; 
                     }
                     // If value is just a string (rare but possible in some schemas), treat it as ID or Name?
                     return { name: key, raw: value };
                 });
                 // Log one item to verify structure
                 if (items.length > 0) {
                    console.log(`[getComponent] Map parsing sample:`, JSON.stringify(items[0]));
                 }
             }

             // Find match using Name, Display Name, or ID (Fuzzy Matching)
             const match = items.find((c: any) => 
                 c.name === componentName || 
                 c.displayName === componentName || 
                 c.id === componentName ||
                 (c.name && c.name.toLowerCase() === componentName.toLowerCase()) ||
                 // Be careful with includes() - false positives!
                 // BUT "PromoBlock" vs "Promo" might need it.
                 // Let's rely on strict or lowercase match first.
                 (c.name && componentName.toLowerCase().includes(c.name.toLowerCase())) 
             );

             // Debug log the search if failing
             if (!match && items.length > 0) {
                 console.log(`[getComponent] No match for '${componentName}'. Available names: ${items.map(i => i.name).slice(0, 5).join(', ')}...`);
             }


             if (match) {
                 console.log(`[getComponent] Resolved '${componentName}' via site list to: ${match.name} (${match.id})`);
                 if (match.id) targetId = match.id;
                 foundDetails = match;
             }
         } catch (e) {
             console.warn(`[getComponent] Resolution via site list failed:`, e);
         }
     }

     // 2. Fallback Resolution: Try Page Context (Allowed Components) if site name lookup failed or wasn't provided
     if ((!isSystemId(targetId) || !foundDetails) && pageId) {
         console.log(`[getComponent] Resolution failed via list. Trying page context for pageId: ${pageId}`);
         const placeholders = ['headless-main', 'main', 'jss-main', 'content'];
         
         for (const ph of placeholders) {
             try {
                // We use a manual fetch here to allow silent failures (no thrown errors for missing PHs)
                const phUrl = `${agentBaseUrl}/api/v1/pages/${pageId}/placeholders/${ph}/allowed-components?language=en`;
                const phRes = await fetch(phUrl, { headers: { Authorization: `Bearer ${accessToken}` } });
                
                if (phRes.ok) {
                    const allowed: any[] = await phRes.json();
                    if (allowed && allowed.length > 0) {
                        const match = allowed.find((c: any) => 
                            c.name === componentName || 
                            c.displayName === componentName || 
                            (c.name && c.name.toLowerCase() === componentName.toLowerCase())
                        );
                        if (match) {
                             console.log(`[getComponent] Resolved '${componentName}' via placeholder '${ph}' to: ${match.name} (${match.id})`);
                             if (match.id) targetId = match.id;
                             foundDetails = match;
                             break;
                        }
                    }
                }
             } catch (e) { /* ignore */ }
         }
     }

     // 3. Fetch Details: Logic Rule - Only fetch by ID
     // We should not expect the API to understand a Name in the ID slot.
     if (!isSystemId(targetId)) {
        console.warn(`[getComponent] '${targetId}' is not a System ID (GUID) and resolution returned no matches. Skipping direct fetch.`);
        // If we found partial details in the list (but maybe no ID?), return that, otherwise null.
        return foundDetails || null;
     }

     const url = `${agentBaseUrl}/api/v1/components/${targetId}`;
     console.log(`[getComponent] Fetching details for ID: ${targetId}`);
     
     const res = await fetch(url, {
         headers: { Authorization: `Bearer ${accessToken}` }
     });

     if (!res.ok) {
         console.warn(`[getComponent] Failed to get component: ${res.status}`);
         return foundDetails || null; 
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

export async function addComponentOnPage(pageId: string, componentName: string, placeholderName: string, language: string, accessToken: string, siteName?: string) {
  try {
     const agentBaseUrl = getAgentApiBaseUrl();
     const url = `${agentBaseUrl}/api/v1/pages/${pageId}/components`;
     
     console.log(`[addComponentOnPage] Resolving Component ID for '${componentName}'...`);
     
     let componentId = '';
     
     // 0. If it's already a GUID, use it directly
     if (isSystemId(componentName)) {
         componentId = componentName;
     } else {
         // 1. Try resolving via getComponent (Global List + Page Context Fallbacks)
         try {
             const resolved = await getComponent(componentName, accessToken, siteName, pageId);
             if (resolved && resolved.id) {
                 componentId = resolved.id;
                 console.log(`[addComponentOnPage] Resolved '${componentName}' via getComponent to: ${resolved.name} (${componentId})`);
             }
         } catch (e) {
             console.warn(`[addComponentOnPage] getComponent resolution failed:`, e);
         }

         // 2. If getComponent failed (or didn't verify ID), try User's Placeholder specifically
         // (getComponent checks specific list of 'main', 'headless-main' etc, but maybe user passed 'content-block')
         if (!componentId) {
             try {
                 console.log(`[addComponentOnPage] Trying placeholder-specific lookup for '${placeholderName}'...`);
                 const allowed = await getAllowedComponents(pageId, placeholderName, language, accessToken);
                 const match = allowed.find((c: any) => 
                    c.name === componentName || 
                    c.displayName === componentName ||
                    (c.name && c.name.toLowerCase() === componentName.toLowerCase())
                 );
                 if (match) {
                     componentId = match.id;
                     console.log(`[addComponentOnPage] Resolved '${componentName}' via allowed-components to: ${componentId}`);
                 }
             } catch (e) {
                 console.warn(`[addComponentOnPage] Failed to lookup component ID in placeholder:`, e);
             }
         }
     }

     if (!componentId) {
         throw new Error(`Could not resolve Component ID for '${componentName}'. Please ensure it is an allowed component in '${placeholderName}' or provide the exact Component ID.`);
     }

     // Generate a unique name for the component instance to avoid duplicate name errors
     // e.g. "Promo-1729384"
     const uniqueSuffix = Date.now().toString().slice(-6);
     // Clean component name for item name usage (remove spaces/special chars if needed, though usually fine)
     const cleanName = componentName.replace(/[^a-zA-Z0-9-_]/g, '');
     const instanceName = `${cleanName}-${uniqueSuffix}`;

     console.log(`[addComponentOnPage] Adding '${instanceName}' (Rendering: ${componentId}) to '${placeholderName}' on page '${pageId}'`);
     
     const res = await fetch(url, {
         method: 'POST',
         headers: {
             Authorization: `Bearer ${accessToken}`,
             'Content-Type': 'application/json'
         },
         body: JSON.stringify({
            componentItemName: instanceName, 
            componentRenderingId: componentId, 
            placeholderPath: placeholderName,  
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

            // General Rule: If an update fails, the schema might be mismatched. 
            // Attempt to retrieve the current item state to provide available fields in the error.
            if (!res.ok) {
                 const errorText = await res.text();
                 
                 // If the request was bad (400) or failed server side (500), 
                 // it's likely due to invalid field data vs schema.
                 if (res.status === 400 || res.status === 500) {
                     try {
                         console.log(`[updateContent] Update failed (${res.status}). Attempting to fetch item schema to assist debugging...`);
                         // Try to fetch the item to see its fields
                         const getUrl = `${agentBaseUrl}/api/v1/content/${params.id}?language=${params.language}&expand=fields`; 
                         const getRes = await fetch(getUrl, { headers: { Authorization: `Bearer ${accessToken}` } });
                         if (getRes.ok) {
                             const itemData = await getRes.json();
                             const availableFields = itemData.fields ? Object.keys(itemData.fields).join(', ') : 'unknown';
                             throw new Error(`Failed to update content item: ${res.status} ${errorText}. \nAVAILABLE FIELDS for this item are: [${availableFields}]. Please retry using these exact field names.`);
                         }
                     } catch (inner: any) {
                         // If we successfully threw the enriched error, let it bubble up.
                         // But if the FETCH failed (getRes not ok) or inner threw something else, just ignore and throw original.
                         if (inner.message && inner.message.includes('AVAILABLE FIELDS')) throw inner;
                     }
                 }
                
                throw new Error(`Failed to update content item: ${res.status} ${errorText}`);
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
       console.log(`[getSitesList] Listing all sites`);
       
       const url = `${agentBaseUrl}/api/v1/sites`;
       const res = await fetch(url, {
           headers: { Authorization: `Bearer ${accessToken}` }
       });
       
       let response;

       if (!res.ok) {
           console.warn(`[getSitesList] Agent API failed (${res.status}). Falling back to xmapps-api.`);
           const fbUrl = 'https://xmapps-api.sitecorecloud.io/api/v1/sites';
           const fbRes = await fetch(fbUrl, {
               headers: { Authorization: `Bearer ${accessToken}` }
           });
           
           if (!fbRes.ok) {
               throw new Error(`Failed to list sites via both Agent API and XM Apps API: ${fbRes.status} ${await fbRes.text()}`);
           }
           response = await fbRes.json();
       } else {
            response = await res.json();
       }
       
       let data: any[] = [];
       if (Array.isArray(response)) {
           data = response;
       } else if (response && (response as any).data && Array.isArray((response as any).data)) {
           data = (response as any).data;
       }

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
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/assets/${assetId}?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get asset info: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get asset info:', error);
        throw error;
    }
}

export async function searchAssets(query: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/assets/search?query=${encodeURIComponent(query)}&language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) {
            if (res.status === 404) {
                 return { results: [] };
            }
            throw new Error(`Failed to search assets: ${res.status} ${await res.text()}`);
        }
        return await res.json();
    } catch (error: any) {
        console.error('Failed to search assets:', error);
        throw error;
    }
}

// NOTE: assetsUploadAsset and assetsUpdateAsset are handled by custom functions at top of file.

export async function createComponentDatasource(name: string, templateId: string, locationId: string, accessToken: string, language: string = 'en') {
    try {
        // Fallback to Content Item creation as args suggest generic item creation
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/content/create`;
        const res = await fetch(url, {
             method: 'POST',
             headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
             body: JSON.stringify({ name, templateId, parentId: locationId, language })
        });
        if (!res.ok) throw new Error(`Failed to create component datasource (content item): ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
         console.error('Failed to create component datasource:', error);
         throw error;
    }
}

export async function searchComponentDatasources(query: string, accessToken: string, language: string = 'en') {
     // NOTE: Original wrapper lacked componentId context. Falling back to generic content/asset search or returning empty?
     // For now, let's try a generic content search or similar if available, or just search assets as fallback.
     console.warn('[searchComponentDatasources] context missing componentId, falling back to asset search pattern for now.');
     return searchAssets(query, accessToken, language);
}

export async function listAvailableInsertOptions(itemId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/content/${itemId}/insert-options?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to list insert options: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to list insert options:', error);
        throw error;
    }
}

export async function addLanguageToPage(pageId: string, language: string, version: number, accessToken: string) {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/pages/${pageId}/add-language`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ language, version })
        });
        if (!res.ok) throw new Error(`Failed to add language to page: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to add language to page:', error);
        throw error;
    }
}

export async function getPagePreviewUrl(pageId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/pages/${pageId}/preview-url?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get preview url: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get page preview url:', error);
        throw error;
    }
}

export async function getPageScreenshot(pageId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/pages/${pageId}/screenshot?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get page screenshot: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get page screenshot:', error);
        throw error;
    }
}

export async function setComponentDatasource(pageId: string, componentId: string, datasourceId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/pages/${pageId}/components/${componentId}/datasource`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ datasourceId, language })
        });
        if (!res.ok) throw new Error(`Failed to set component datasource: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to set component datasource:', error);
        throw error;
    }
}

export async function createPersonalizationVersion(pageId: string, conditionId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/personalization/${pageId}/versions`;
        const res = await fetch(url, {
            method: 'POST',
            headers: { Authorization: `Bearer ${accessToken}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ conditionId, language })
        });
        if (!res.ok) throw new Error(`Failed to create personalization version: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to create personalization version:', error);
        throw error;
    }
}

export async function getPersonalizationVersionsByPage(pageId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/personalization/by-page/${pageId}?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get personalization versions: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get personalization versions:', error);
        throw error;
    }
}

export async function getSiteDetails(siteName: string, accessToken: string) {
    try {
        // Resolve site by name from list
        const sites = await getSitesList(accessToken);
        const match = sites.find((s:any) => s.name === siteName);
        if (!match) {
             throw new Error(`Site '${siteName}' not found`);
        }
        return match;
    } catch (error: any) {
        console.error('Failed to get site details:', error);
        throw error;
    }
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
    try {
        const xmappsBaseUrl = 'https://xmapps-api.sitecorecloud.io';
        console.log(`[deleteSite] Deleting site: ${siteId} via XM Apps API`);
        const url = `${xmappsBaseUrl}/api/v1/sites/${siteId}`;
        const res = await fetch(url, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        if (!res.ok) throw new Error(`Failed to delete site: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to delete site via Agent API:', error);
        throw error;
    }
}

export async function listPageChildren(itemId: string, accessToken: string, language: string = 'en', siteId?: string) {
  try {
     if (!siteId) {
         throw new Error('siteId is required to list page children via Agent API fallback.');
     }

     // STRATEGY CHANGE: Use Service Token if available.
     // The Agent API endpoints (used by getPage, getAllPagesForSite) generally require a Service Token (Client Credentials).
     // User Tokens often fail with "Failed to extract claims".
     // We try to upgrade to a Service Token to perform this read operation reliably.
     let serviceToken = null;
     try {
        serviceToken = await getClientCredentialsJwt();
     } catch (tokenErr) {
        console.warn(`[listPageChildren] Service Token request failed (${(tokenErr as any).message}). Continuing with User Token.`);
     }

     const tokenToUse = serviceToken || accessToken;
     
     if (serviceToken) {
         console.log(`[listPageChildren] Using Service Token for reliable Agent API access.`);
     } else {
         console.warn(`[listPageChildren] No Service Token available. Using User Token (may fail on Agent API).`);
     }

     console.log(`[listPageChildren] Using getAllPagesForSite logic to find children of ${itemId}`);
     
     // 1. Get All Pages for the Site first
     // This uses the tokenToUse (Service Token preferred)
     console.log(`[listPageChildren] Fetching all pages to resolve hierarchy...`);
     const allPages = await getAllPagesForSite(siteId, language, tokenToUse, '');

     // 2. Find Parent Page within the list
     const parentPage = allPages.find((p: any) => p.id === itemId);

     if (!parentPage || !parentPage.path) {
         console.warn(`[listPageChildren] Parent ${itemId} not found in site list. Checking directly via getPage...`);
         // Emergency fallback: Try to fetch the parent page directly (in case it's not in the list for some reason)
         try {
             const directParent = await getPage(itemId, language, tokenToUse);
             if (directParent && directParent.path) {
                 const pPath = directParent.path.endsWith('/') ? directParent.path : directParent.path + '/';
                 return filterChildren(allPages, itemId, pPath);
             }
         } catch (e) {
            // Ignore
         }
         throw new Error(`Could not resolve parent page path for itemId: ${itemId} within site listing.`);
     }

     const parentPath = parentPage.path.endsWith('/') ? parentPage.path : parentPage.path + '/';
     console.log(`[listPageChildren] Parent Path: ${parentPath}`);
     
     return filterChildren(allPages, itemId, parentPath);

  } catch (error: any) {
    console.error('Failed to list children via Agent API Fallback:', error);
    throw error;
  }
}

function filterChildren(allPages: any[], parentId: string, parentPath: string) {
     const children = allPages.filter((p: any) => {
         // Filter out the parent itself
         if (p.id === parentId || p.path === parentPath.slice(0, -1)) return false;
         
         const pPath = p.path;
         if (!pPath.startsWith(parentPath)) return false;
         
         const relative = pPath.substring(parentPath.length);
         // If relative path has no slashes, it's a direct child. 
         return !relative.includes('/');
     });

     console.log(`[listPageChildren] Success. Found ${children.length} children.`);
     return children;
}


// --- Comprehensive Site Management Wrappers ---

export async function getFavoriteSiteTemplates(accessToken: string) {
    try {
        const xmappsBaseUrl = 'https://xmapps-api.sitecorecloud.io';
        const url = `${xmappsBaseUrl}/api/v1/favorites/sitetemplates`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get favorite site templates: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get favorite site templates:', error);
        throw error;
    }
}

export async function listSiteTemplates(accessToken: string) {
  try {
      const xmappsBaseUrl = 'https://xmapps-api.sitecorecloud.io'; 
      const url = `${xmappsBaseUrl}/api/v1/sites/templates`;
      console.log(`[listSiteTemplates] fetching from: ${url}`);
      
      const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
      if (!res.ok) throw new Error(`Failed to list site templates: ${res.status} ${await res.text()}`);

      const response = await res.json();
      console.log(`[listSiteTemplates] Raw Response:`, JSON.stringify(response, null, 2));

      let templates: any[] = [];
      if (Array.isArray(response)) {
          templates = response;
      } else if (response && (response as any).templates && Array.isArray((response as any).templates)) {
          templates = (response as any).templates;
      } else if (response && (response as any).data && Array.isArray((response as any).data)) {
          templates = (response as any).data;
      } else if (response && (response as any).items && Array.isArray((response as any).items)) {
          templates = (response as any).items;
      }

      console.log(`[listSiteTemplates] Success. Found ${templates.length} templates.`);
      return templates;
    } catch (error: any) {
      console.error('Failed to list site templates via SDK:', error);
      throw error;
    }
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
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/personalization/condition-templates?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get condition templates: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get condition templates:', error);
        throw error;
    }
}

export async function getConditionTemplateById(templateId: string, accessToken: string, language: string = 'en') {
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/personalization/condition-templates/${templateId}?language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get condition template by id: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get condition template by id:', error);
        throw error;
    }
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
    try {
        const agentBaseUrl = getAgentApiBaseUrl();
        const url = `${agentBaseUrl}/api/v1/pages/template-by-id?templateId=${templateId}&language=${language}`;
        const res = await fetch(url, { headers: { Authorization: `Bearer ${accessToken}` } });
        if (!res.ok) throw new Error(`Failed to get page template by id: ${res.status} ${await res.text()}`);
        return await res.json();
    } catch (error: any) {
        console.error('Failed to get page template by id:', error);
        throw error;
    }
}








