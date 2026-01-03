// MCP Client for Sitecore Search Server

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

export interface SitecoreSearchTool {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}

export class SitecoreSearchMCPClient {
  private client: Client | null = null;
  private transport: StdioClientTransport | null = null;
  private availableTools: SitecoreSearchTool[] = [];
  private connected: boolean = false;

  async connect(): Promise<void> {
    if (this.connected && this.client) {
      return;
    }

    try {
      // For local development or Railway deployment
      // The MCP server runs as a separate process
      this.transport = new StdioClientTransport({
        command: 'npx',
        args: ['-y', '@markstiles/sitecore-search-mcp'],
        env: {
          SITECORE_DOMAIN_ID: process.env.SITECORE_DOMAIN_ID || '',
          SITECORE_CLIENT_KEY: process.env.SITECORE_CLIENT_KEY || '',
          SITECORE_API_KEY: process.env.SITECORE_API_KEY || '',
        }
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
      this.availableTools = toolsResponse.tools as SitecoreSearchTool[];
      
      this.connected = true;
      console.log(`Connected to Sitecore Search MCP. Available tools: ${this.availableTools.length}`);
    } catch (error) {
      console.error('Failed to connect to Sitecore Search MCP:', error);
      throw error;
    }
  }

  async disconnect(): Promise<void> {
    if (this.client && this.transport) {
      await this.client.close();
      this.connected = false;
      this.client = null;
      this.transport = null;
    }
  }

  async callTool(toolName: string, args: Record<string, unknown>): Promise<unknown> {
    if (!this.connected || !this.client) {
      await this.connect();
    }

    try {
      const result = await this.client!.callTool({
        name: toolName,
        arguments: args,
      });

      return result.content;
    } catch (error) {
      console.error(`Error calling tool ${toolName}:`, error);
      throw error;
    }
  }

  getAvailableTools(): SitecoreSearchTool[] {
    return this.availableTools;
  }

  isConnected(): boolean {
    return this.connected;
  }

  // Typed helper methods for common operations

  async searchContent(params: {
    domainId?: string;
    rfkId: string;
    keyphrase?: string;
    entity?: string;
    page?: number;
    limit?: number;
  }): Promise<unknown> {
    return this.callTool('sitecore_search_query', {
      domainId: params.domainId || process.env.SITECORE_DOMAIN_ID,
      ...params,
    });
  }

  async searchWithFacets(params: {
    domainId?: string;
    rfkId: string;
    keyphrase?: string;
    facets?: Array<{ name: string; type: string; values?: string[] }>;
    sort?: Record<string, string>;
    page?: number;
    limit?: number;
  }): Promise<unknown> {
    return this.callTool('sitecore_search_with_facets', {
      domainId: params.domainId || process.env.SITECORE_DOMAIN_ID,
      ...params,
    });
  }

  async getRecommendations(params: {
    domainId?: string;
    rfkId: string;
    recommendationId?: string;
    entity?: string;
    userId?: string;
    limit?: number;
  }): Promise<unknown> {
    return this.callTool('sitecore_get_recommendations', {
      domainId: params.domainId || process.env.SITECORE_DOMAIN_ID,
      ...params,
    });
  }

  async aiSearch(params: {
    domainId?: string;
    rfkId: string;
    keyphrase: string;
    type: 'answer' | 'question';
    entity?: string;
  }): Promise<unknown> {
    return this.callTool('sitecore_ai_search', {
      domainId: params.domainId || process.env.SITECORE_DOMAIN_ID,
      ...params,
    });
  }

  async trackEvent(params: {
    domainId?: string;
    customerKey?: string;
    eventType: string;
    value?: Record<string, unknown>;
    context?: Record<string, unknown>;
  }): Promise<unknown> {
    return this.callTool('sitecore_track_event', {
      domainId: params.domainId || process.env.SITECORE_DOMAIN_ID,
      customerKey: params.customerKey || process.env.SITECORE_CLIENT_KEY,
      ...params,
    });
  }
}

// Singleton instance for reuse across requests
let mcpClientInstance: SitecoreSearchMCPClient | null = null;

export async function getMCPClient(): Promise<SitecoreSearchMCPClient> {
  if (!mcpClientInstance) {
    mcpClientInstance = new SitecoreSearchMCPClient();
    await mcpClientInstance.connect();
  } else if (!mcpClientInstance.isConnected()) {
    await mcpClientInstance.connect();
  }
  
  return mcpClientInstance;
}

export async function disconnectMCPClient(): Promise<void> {
  if (mcpClientInstance) {
    await mcpClientInstance.disconnect();
    mcpClientInstance = null;
  }
}
