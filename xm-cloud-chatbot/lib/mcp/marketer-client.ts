// MCP Client for Marketer-MCP with OAuth support

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { prisma } from '@/lib/db';
import { isDatabaseUnavailableError } from '@/lib/utils/db-errors';

export interface MarketerMCPTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export class MarketerMCPClient {
  private client: Client | null = null;
  private transport: StreamableHTTPClientTransport | null = null;
  private availableTools: MarketerMCPTool[] = [];
  private connected: boolean = false;
  private userId: string;
  private accessToken: string | null = null;

  private debugEnabled: boolean =
    process.env.MARKETER_MCP_DEBUG === 'true' || process.env.MARKETER_MCP_DEBUG === '1';

  constructor(userId: string) {
    this.userId = userId;
  }

  private redactHeaders(headers: Headers): Record<string, string> {
    const entries = Object.fromEntries(headers.entries());
    for (const key of Object.keys(entries)) {
      const lower = key.toLowerCase();
      if (lower === 'authorization' || lower === 'cookie' || lower === 'set-cookie') {
        entries[key] = '[redacted]';
      }
    }
    return entries;
  }

  private safeJson(value: unknown, maxLen = 8000): string {
    try {
      const seen = new WeakSet<object>();
      const json = JSON.stringify(
        value,
        (_key, val) => {
          if (typeof val === 'string') {
            return val.length > 2000 ? `${val.slice(0, 2000)}…[truncated ${val.length}]` : val;
          }
          if (typeof val === 'object' && val !== null) {
            if (seen.has(val as object)) return '[circular]';
            seen.add(val as object);
          }
          return val;
        },
        2
      );
      return json.length > maxLen ? `${json.slice(0, maxLen)}…[truncated ${json.length}]` : json;
    } catch {
      return '[unserializable]';
    }
  }

  private debugLog(message: string, details?: unknown): void {
    if (!this.debugEnabled) return;
    if (details !== undefined) {
      console.log(message, details);
    } else {
      console.log(message);
    }
  }

  private normalizeUrl(value: unknown): string | null {
    if (typeof value !== 'string') return null;
    return value.replace(/\/+$/, '');
  }

  private getExpectedIssuer(): string {
    const authUrl = process.env.OAUTH_AUTHORIZATION_URL;
    if (authUrl) {
      try {
        return new URL(authUrl).origin.replace(/\/+$/, '');
      } catch {
        // fall through
      }
    }
    return 'https://edge-platform.sitecorecloud.io';
  }

  private getExpectedResource(): string {
    return (
      process.env.OAUTH_RESOURCE ||
      process.env.OAUTH_AUDIENCE ||
      process.env.MARKETER_MCP_URL ||
      'https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod'
    ).replace(/\/+$/, '');
  }

  private isJwt(token: string): boolean {
    // JWTs have at least header.payload
    return typeof token === 'string' && token.split('.').length >= 2;
  }

  private decodeJwt(token: string): any {
    if (!this.isJwt(token)) {
      throw new Error('Token is not a JWT (opaque)');
    }

    const base64Url = token.split('.')[1];
    if (!base64Url) {
      throw new Error('Token is missing JWT payload');
    }

    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      Buffer.from(base64, 'base64')
        .toString()
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  }

  private tokenMatchesMcp(token: string): boolean {
    try {
      // If we can't inspect claims locally, treat as "matches" and let the server validate.
      if (!this.isJwt(token)) {
        return true;
      }

      const payload = this.decodeJwt(token);
      const expectedIssuer = this.getExpectedIssuer();
      const expectedResource = this.getExpectedResource();

      const tokenIss = this.normalizeUrl(payload?.iss);
      const issOk = tokenIss === expectedIssuer;

      const aud = payload?.aud;
      const tokenAud = this.normalizeUrl(aud);
      const tokenAudList = Array.isArray(aud)
        ? aud.map((a) => this.normalizeUrl(a)).filter(Boolean)
        : [];
      const audOk =
        tokenAud === expectedResource ||
        tokenAudList.includes(expectedResource) ||
        this.normalizeUrl(payload?.resource) === expectedResource;

      return !!(issOk && audOk);
    } catch {
      return false;
    }
  }

  private async getAccessToken(): Promise<string> {
    // Get token from database
    const tokenRecord = await prisma.oAuthToken.findUnique({
      where: { userId: this.userId },
    });

    if (!tokenRecord) {
      throw new Error('No OAuth token found. User needs to authenticate.');
    }

    // Validate token issuer/audience for Marketer MCP (JWTs only)
    try {
      if (this.isJwt(tokenRecord.accessToken)) {
        const payload = this.decodeJwt(tokenRecord.accessToken);
        console.log('[Marketer MCP] Token scope:', payload.scope);
        console.log('[Marketer MCP] Token issuer:', payload.iss);
        console.log('[Marketer MCP] Token audience:', payload.aud);
        if (payload.resource) {
          console.log('[Marketer MCP] Token resource:', payload.resource);
        }
        console.log('[Marketer MCP] Token issued at:', new Date(payload.iat * 1000).toISOString());

        if (!this.tokenMatchesMcp(tokenRecord.accessToken)) {
          console.warn('[Marketer MCP] Stored token does not match expected issuer/resource. Forcing re-auth.', {
            expectedIssuer: this.getExpectedIssuer(),
            expectedResource: this.getExpectedResource(),
            tokenIssuer: payload?.iss,
            tokenAud: payload?.aud,
            tokenResource: payload?.resource,
          });
          await prisma.oAuthToken.delete({ where: { userId: this.userId } }).catch(() => undefined);
          throw new Error('Stored OAuth token is not valid for Marketer MCP. User needs to re-authenticate.');
        }
      } else {
        console.log('[Marketer MCP] Stored access_token is opaque (not a JWT); skipping local claim validation.');
      }
    } catch (err) {
      if (err instanceof Error && err.message.includes('User needs to re-authenticate')) {
        throw err;
      }
      console.warn('[Marketer MCP] Could not decode/validate token:', err);
    }

    // Check if token is expired (with 5-minute buffer)
    const isExpired = tokenRecord.expiresAt.getTime() - Date.now() < 5 * 60 * 1000;

    if (isExpired) {
      // Try to refresh the token
      if (tokenRecord.refreshToken) {
        await this.refreshAccessToken();
        // Fetch the updated token
        const updatedToken = await prisma.oAuthToken.findUnique({
          where: { userId: this.userId },
        });
        if (updatedToken) {
          return updatedToken.accessToken;
        }
      }
      throw new Error('OAuth token expired and refresh failed. User needs to re-authenticate.');
    }

    return tokenRecord.accessToken;
  }

  private async refreshAccessToken(): Promise<void> {
    const response = await fetch(`${process.env.NEXT_PUBLIC_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ userId: this.userId }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh access token');
    }
  }



  async connect(): Promise<void> {
    if (this.connected && this.client) {
      return;
    }

    try {
      // Get access token
      this.accessToken = await this.getAccessToken();
      console.log('[Marketer MCP] Access token retrieved:', this.accessToken ? `${this.accessToken.substring(0, 20)}...` : 'null');

      // Connect to marketer-mcp server using Streamable HTTP transport.
      // This transport tolerates GET 405 (no dedicated SSE stream endpoint) and will still work via POST.
      const mcpUrl = process.env.MARKETER_MCP_URL || 'https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod';
      console.log('[Marketer MCP] Connecting to:', mcpUrl);

      // Note: Streamable HTTP uses an optional GET (SSE) channel for server->client messages.
      // The Sitecore endpoint may return 405 for that GET, which is expected and handled by the SDK.
      
      // Create Streamable HTTP transport with custom fetch that includes auth headers
      this.transport = new StreamableHTTPClientTransport(new URL(mcpUrl), {
        fetch: async (url: string | URL | Request, init?: RequestInit) => {
          const requestId = Math.random().toString(16).slice(2);
          const method = init?.method || 'GET';
          const headers = new Headers(init?.headers);
          if (!headers.has('Authorization')) {
            headers.set('Authorization', `Bearer ${this.accessToken}`);
          }

          const redactedHeaders = this.redactHeaders(headers);

          let bodyPreview: string | undefined;
          const body = init?.body as unknown;
          if (typeof body === 'string') {
            // Often JSON-RPC payload for tool calls
            bodyPreview = body.length > 8000 ? `${body.slice(0, 8000)}…[truncated ${body.length}]` : body;
          } else if (body instanceof Uint8Array) {
            bodyPreview = `[Uint8Array length=${body.length}]`;
          } else if (body && typeof body === 'object') {
            bodyPreview = `[body type=${(body as any).constructor?.name || 'object'}]`;
          }

          this.debugLog('[Marketer MCP] HTTP request', {
            requestId,
            method,
            url: String(url),
            headers: redactedHeaders,
            bodyPreview,
          });

          const start = Date.now();
          const response = await fetch(url, {
            ...init,
            headers,
          });

          const durationMs = Date.now() - start;
          const contentType = response.headers.get('content-type') || '';

          // Streamable HTTP spec allows servers to not support the optional SSE GET endpoint.
          // The MCP SDK treats GET 405 as an expected/handled case; avoid noisy logs and avoid
          // cloning/reading the body here to prevent any interaction with response cancellation.
          if (method === 'GET' && response.status === 405 && (headers.get('Accept') || '').includes('text/event-stream')) {
            this.debugLog('[Marketer MCP] SSE GET not supported (405); continuing.');
            return response;
          }

          if (response.status >= 400) {
            // Always emit error diagnostics (safe/redacted), even if debug is off.
            let responseBodyPreview: string | undefined;
            if (!contentType.includes('text/event-stream')) {
              try {
                const cloned = response.clone();
                const text = await cloned.text();
                responseBodyPreview = text.length > 4000 ? `${text.slice(0, 4000)}…[truncated ${text.length}]` : text;
              } catch {
                // ignore
              }
            }

            console.warn('[Marketer MCP] HTTP error', {
              requestId,
              method,
              url: String(url),
              status: response.status,
              durationMs,
              contentType,
              requestHeaders: redactedHeaders,
              requestBodyPreview: bodyPreview,
              responseBodyPreview,
            });
          }

          // For non-stream responses, include a small preview of body to help debug.
          if (this.debugEnabled && !contentType.includes('text/event-stream')) {
            try {
              const cloned = response.clone();
              const text = await cloned.text();
              const textPreview = text.length > 4000 ? `${text.slice(0, 4000)}…[truncated ${text.length}]` : text;
              this.debugLog('[Marketer MCP] HTTP response', {
                requestId,
                status: response.status,
                durationMs,
                contentType,
                bodyPreview: textPreview,
              });
            } catch (e) {
              this.debugLog('[Marketer MCP] HTTP response (preview failed)', {
                requestId,
                status: response.status,
                durationMs,
                contentType,
                error: String(e),
              });
            }
          } else {
            this.debugLog('[Marketer MCP] HTTP response', {
              requestId,
              status: response.status,
              durationMs,
              contentType,
            });
          }

          // If this looks like JSON-RPC, attempt to parse and log a structured view
          if (this.debugEnabled && typeof body === 'string' && body.trim().startsWith('{')) {
            try {
              const parsed = JSON.parse(body);
              this.debugLog('[Marketer MCP] HTTP request JSON (parsed)', this.safeJson(parsed));
            } catch {
              // ignore
            }
          }

          return response;
        },
      });

      this.client = new Client(
        {
          name: 'xm-cloud-chatbot',
          version: '1.0.0',
        },
        {
          capabilities: {},
        }
      );

      await this.client.connect(this.transport);
      
      // Discover available tools
      const toolsResponse = await this.client.listTools();
      this.availableTools = toolsResponse.tools as MarketerMCPTool[];
      
      this.connected = true;
      console.log(`Connected to Marketer MCP. Available tools: ${this.availableTools.length}`);
    } catch (error) {
      console.error('Failed to connect to Marketer MCP:', error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    if (this.client && this.transport) {
      await this.client.close();
      this.connected = false;
      this.client = null;
      this.transport = null;
      this.accessToken = null;
    }
  }

  async callTool(toolName: string, args: Record<string, unknown>): Promise<unknown> {
    if (!this.connected || !this.client) {
      await this.connect();
    }

    try {
      // Ensure we have a fresh token before making the call
      if (this.accessToken) {
        const tokenRecord = await prisma.oAuthToken.findUnique({
          where: { userId: this.userId },
        });
        
        if (tokenRecord) {
          const isExpired = tokenRecord.expiresAt.getTime() - Date.now() < 5 * 60 * 1000;
          if (isExpired) {
            // Reconnect with fresh token
            await this.disconnect();
            await this.connect();
          }
        }
      }

      this.debugLog('[Marketer MCP] callTool()', {
        toolName,
        args: this.safeJson(args),
      });

      const result = await this.client!.callTool({
        name: toolName,
        arguments: args,
      });

      this.debugLog('[Marketer MCP] callTool() result', {
        toolName,
        contentPreview: this.safeJson(result.content, 6000),
      });

      return result.content;
    } catch (error) {
      console.error(`Error calling tool ${toolName}:`, error);
      
      // If auth error, try to reconnect once
      if (error instanceof Error && error.message.includes('401')) {
        await this.disconnect();
        await this.connect();
        
        // Retry the call
        const result = await this.client!.callTool({
          name: toolName,
          arguments: args,
        });
        return result.content;
      }
      
      throw error;
    }
  }

  getAvailableTools(): MarketerMCPTool[] {
    return this.availableTools;
  }

  isConnected(): boolean {
    return this.connected;
  }
}

// Global client instance cache (per user)
const clientCache = new Map<string, MarketerMCPClient>();

export async function getMarketerMCPClient(userId: string): Promise<MarketerMCPClient> {
  let client = clientCache.get(userId);
  
  if (!client) {
    client = new MarketerMCPClient(userId);
    clientCache.set(userId, client);
  }

  // Ensure connection
  if (!client.isConnected()) {
    await client.connect();
  }

  return client;
}

// Helper to check if user needs authentication
export async function checkMarketerMCPAuth(userId: string): Promise<{
  authenticated: boolean;
  requiresAuth: boolean;
  dbUnavailable?: boolean;
}> {
  try {
    const tokenRecord = await prisma.oAuthToken.findUnique({
      where: { userId },
    });

    if (!tokenRecord) {
      return { authenticated: false, requiresAuth: true };
    }

    // Check if token is expired (with 5-minute buffer)
    const isExpired = tokenRecord.expiresAt.getTime() - Date.now() < 5 * 60 * 1000;
    if (isExpired) {
      return { authenticated: false, requiresAuth: true };
    }

    // If the access token is opaque (not a JWT), we can't validate iss/aud locally.
    // In that case, treat it as valid based on expiry and let the MCP call decide.
    if (!tokenRecord.accessToken.includes('.')) {
      return { authenticated: true, requiresAuth: false };
    }

    // Also validate issuer/resource to avoid using a token from a different auth server.
    try {
      const expectedIssuer = (process.env.OAUTH_AUTHORIZATION_URL
        ? new URL(process.env.OAUTH_AUTHORIZATION_URL).origin
        : 'https://edge-platform.sitecorecloud.io'
      ).replace(/\/+$/, '');
      const expectedResource = (
        process.env.OAUTH_RESOURCE ||
        process.env.OAUTH_AUDIENCE ||
        process.env.MARKETER_MCP_URL ||
        'https://edge-platform.sitecorecloud.io/mcp/marketer-mcp-prod'
      ).replace(/\/+$/, '');

      const base64Url = tokenRecord.accessToken.split('.')[1];
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
      const jsonPayload = decodeURIComponent(
        Buffer.from(base64, 'base64')
          .toString()
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      );
      const payload = JSON.parse(jsonPayload);

      const tokenIss = typeof payload?.iss === 'string' ? payload.iss.replace(/\/+$/, '') : undefined;
      const issOk = tokenIss === expectedIssuer;
      const aud = payload?.aud;
      const tokenAud = typeof aud === 'string' ? aud.replace(/\/+$/, '') : undefined;
      const tokenAudList = Array.isArray(aud)
        ? aud
            .map((a) => (typeof a === 'string' ? a.replace(/\/+$/, '') : null))
            .filter(Boolean)
        : [];
      const audOk =
        tokenAud === expectedResource ||
        tokenAudList.includes(expectedResource) ||
        (typeof payload?.resource === 'string' && payload.resource.replace(/\/+$/, '') === expectedResource);

      if (!issOk || !audOk) {
        await prisma.oAuthToken.delete({ where: { userId } }).catch(() => undefined);
        return { authenticated: false, requiresAuth: true };
      }
    } catch {
      // If we can't decode (unexpected), avoid forcing re-auth loops.
      // Fall back to expiry-based validity and let the MCP connection validate.
      return { authenticated: true, requiresAuth: false };
    }

    return { authenticated: true, requiresAuth: false };
  } catch (error) {
    console.error('Error checking Marketer MCP auth:', error);
    if (isDatabaseUnavailableError(error)) {
      return { authenticated: false, requiresAuth: false, dbUnavailable: true };
    }
    return { authenticated: false, requiresAuth: true };
  }
}
