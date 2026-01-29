import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { prisma } from '@/lib/db';
import { getMarketerMCPClient, checkMarketerMCPAuth, MarketerMCPTool } from '@/lib/mcp/marketer-client';
import { getAllTools, CLIENT_CONTEXT_TOOLS, CLIENT_ACTION_TOOLS, IMAGE_GENERATION_TOOL, ASSET_URL_TOOL } from '@/lib/mcp/tools';
import { getAssistantConfig, ContextValues } from '@/lib/prompts';
import { classifyIntent } from '@/lib/utils/classify-intent';
import { generateConversationTitle } from '@/lib/utils/generate-title';
import { AssistantType } from '@/lib/types/assistant';
import { 
  hasAgentApiCredentialsConfigured, 
  uploadAssetViaAgentApi, 
  updateAssetViaAgentApi,
  getAllPagesForSite,
  getComponentsOnPage,
  getAllowedComponents,
  getPage,
  getPageHtml,
  getPagePathByUrl,
  searchSite,
  listComponents,
  getComponent,
  getClientCredentialsJwt,
  createPage,
  addComponentOnPage,
  createContentItem,
  updateContent,
  deleteContent,
  getSitesList,
  listSiteCollections,
  getFavoriteSites,
  listLanguages,
  aggregatePageData,
  listJobs,
  searchAssets,
  createComponentDatasource,
  getPagePreviewUrl,
  setComponentDatasource,
  duplicatePage,
  listPageChildren,
  listSiteTemplates,
  getRenderingHosts,
  retrievePageVersions,
  getConditionTemplates,
  getPageTemplateById
} from '@/lib/sitecore/agent-api';
import { getDatabaseUnavailableHint, isDatabaseUnavailableError } from '@/lib/utils/db-errors';
import { buildEdgeAssetUrl } from '@/lib/utils/edge-asset-url';
import { extractChatAssetsFromToolResult } from '@/lib/utils/chat-assets';
import { getSmartToken } from '@/lib/utils/server-auth-helpers';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const CHAT_API_DEBUG = process.env.CHAT_API_DEBUG
  ? process.env.CHAT_API_DEBUG === 'true' || process.env.CHAT_API_DEBUG === '1'
  : process.env.NODE_ENV === 'development';
const debugLog = (...args: unknown[]) => {
  if (CHAT_API_DEBUG) {
    console.log(...args);
  }
};

const MAX_INLINE_IMAGE_BYTES = 2_000_000; // keep well under typical model limits (base64 expands ~33%)

function withSearchParam(url: string, key: string, value: string): string {
  try {
    const u = new URL(url);
    if (!u.searchParams.has(key)) u.searchParams.set(key, value);
    return u.toString();
  } catch {
    return url;
  }
}

async function tryFetchImageAsDataUrl(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8_000);

    const response = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      // Avoid caching surprises when assets are updated.
      cache: 'no-store',
    });

    clearTimeout(timeout);

    if (!response.ok) return null;

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.toLowerCase().startsWith('image/')) return null;

    const contentLengthHeader = response.headers.get('content-length');
    const contentLength = contentLengthHeader ? Number(contentLengthHeader) : NaN;
    if (Number.isFinite(contentLength) && contentLength > MAX_INLINE_IMAGE_BYTES) {
      return null;
    }

    const arrayBuffer = await response.arrayBuffer();
    if (arrayBuffer.byteLength > MAX_INLINE_IMAGE_BYTES) return null;

    const base64 = Buffer.from(arrayBuffer).toString('base64');
    return `data:${contentType};base64,${base64}`;
  } catch {
    return null;
  }
}

// Helper function to clean up incomplete markdown image syntax
function cleanIncompleteMarkdown(text: string): string {
  // Remove incomplete markdown image syntax like "![alt](" or "![alt text]("
  return text
    .replace(/!\[[^\]]*\]\(\s*$/g, '') // Remove incomplete ![alt](
    .replace(/!\[[^\]]*$/g, '')          // Remove incomplete ![alt
    .trim();
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const {
      conversationId,
      message,
      userId,
      siteId,
      currentPageId,
      selectedAsset,
      applicationId,
      applicationContext,
      pagesContext,
      siteContext,
      hostUser,
    } = body;

    debugLog('[Chat API] Auth Check Params:', { 
      userId, 
      applicationId, 
      hasAgentId: Boolean(process.env.SITECORE_AGENT_API_CLIENT_ID),
      hasAgentSecret: Boolean(process.env.SITECORE_AGENT_API_CLIENT_SECRET)
    });

    if (!message || !userId || !siteId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Check if user is authenticated for marketer-mcp
    const authStatus = await checkMarketerMCPAuth(userId, applicationId);
    if (authStatus.dbUnavailable) {
      return NextResponse.json(
        {
          error: 'Database unavailable',
          code: 'DB_UNAVAILABLE',
          message: getDatabaseUnavailableHint(),
        },
        { status: 503 }
      );
    }
    if (authStatus.requiresAuth) {
      debugLog('[Chat API] Marketer MCP auth required; continuing without Marketer MCP tools.');
    }

    // Get or create conversation
    let conversation = conversationId
      ? await prisma.conversation.findUnique({
          where: { id: conversationId },
          include: { messages: { orderBy: { timestamp: 'asc' } } },
        })
      : null;
    debugLog('Conversation fetched:', conversation?.id || 'new conversation');

    // Get conversation history
    const conversationHistory = conversation?.messages.map((m: { role: string; content: string }) => ({
      role: m.role,
      content: m.content,
    })) || [];
    debugLog('Conversation history length:', conversationHistory.length);

    // Classify intent (initial or reclassification)
    const intentResult = await classifyIntent(
      message,
      conversationHistory.length > 0 ? conversationHistory : undefined,
      conversation?.assistantType as AssistantType | undefined
    );
    debugLog('Intent classification result:', intentResult);

    // Create new conversation if needed
    if (!conversation) {
      conversation = await prisma.conversation.create({
        data: {
          userId,
          siteId,
          assistantType: intentResult.assistantType,
          metadata: { 
            currentPageId,
            applicationId,
            environmentHost: process.env.ENVIRONMENT_HOST,
            applicationContext,
            pagesContext,
            siteContext,
            hostUser,
          },
        },
        include: { messages: true },
      });
    } else {
      // Always update conversation context/metadata so we have the latest page/app info
      const currentMeta = (conversation.metadata as Record<string, any>) || {};
      const newMeta = {
        ...currentMeta,
        currentPageId: currentPageId || currentMeta.currentPageId,
        applicationId: applicationId || currentMeta.applicationId,
        environmentHost: process.env.ENVIRONMENT_HOST || currentMeta.environmentHost,
        applicationContext: applicationContext || currentMeta.applicationContext,
        pagesContext: pagesContext || currentMeta.pagesContext,
        siteContext: siteContext || currentMeta.siteContext,
        hostUser: hostUser || currentMeta.hostUser,
      };

      conversation = await prisma.conversation.update({
        where: { id: conversation.id },
        data: { 
          assistantType: intentResult.shouldSwitch ? intentResult.assistantType : undefined,
          siteId: siteId, // Ensure siteId is current
          metadata: newMeta,
        },
        include: { messages: { orderBy: { timestamp: 'asc' } } },
      });

      if (intentResult.shouldSwitch) {
        // Track assistant switch in analytics
        await prisma.analytics.create({
          data: {
            conversationId: conversation.id,
            eventType: 'assistant_switch',
            eventData: {
              from: conversation.assistantType,
              to: intentResult.assistantType,
              confidence: intentResult.confidence,
              reasoning: intentResult.reasoning,
            },
          },
        });
      }
    }

    // Save user message
    const userMessage = await prisma.message.create({
      data: {
        conversationId: conversation.id,
        role: 'user',
        content: message,
        currentPageId,
      },
    });

    // Get assistant configuration
    const pagesContextInfo = pagesContext || (conversation.metadata as any)?.pagesContext;
    const appContextInfo = applicationContext || (conversation.metadata as any)?.applicationContext;
    const siteName = pagesContextInfo?.siteInfo?.name;
    const currentPageName =
      pagesContextInfo?.pageInfo?.displayName || pagesContextInfo?.pageInfo?.name;
    const currentPagePath = pagesContextInfo?.pageInfo?.path;
    const tenantDisplayName = appContextInfo?.tenantDisplayName;

    const assistantConfig = getAssistantConfig(
      conversation.assistantType as AssistantType,
      {
        currentPageId,
        currentPageName,
        currentPagePath,
        siteId,
        siteName,
        userId,
        applicationId,
        environmentHost: process.env.ENVIRONMENT_HOST,
        tenantDisplayName,
        applicationContext: appContextInfo,
        isMarketerAuthRequired: authStatus.requiresAuth
      }
    );

    // Prepare messages for OpenAI
    const assetUrl = buildEdgeAssetUrl({
      assetId: selectedAsset?.itemId,
      explicitUrl: selectedAsset?.url,
    });

    const selectedAssetText = selectedAsset
      ? [
          'Selected asset context (from media library):',
          selectedAsset.itemId ? `- itemId: ${selectedAsset.itemId}` : null,
          selectedAsset.path ? `- path: ${selectedAsset.path}` : null,
          selectedAsset.type ? `- type: ${selectedAsset.type}` : null,
          selectedAsset.altText ? `- altText: ${selectedAsset.altText}` : null,
          typeof selectedAsset.width === 'number' ? `- width: ${selectedAsset.width}` : null,
          typeof selectedAsset.height === 'number' ? `- height: ${selectedAsset.height}` : null,
          selectedAsset.extension ? `- extension: ${selectedAsset.extension}` : null,
          typeof selectedAsset.size === 'number' ? `- size: ${selectedAsset.size}` : null,
          selectedAsset.description ? `- description: ${selectedAsset.description}` : null,
          assetUrl ? `- url: ${assetUrl}` : null,
          `- environmentHost: ${process.env.ENVIRONMENT_HOST}`,
        ]
          .filter(Boolean)
          .join('\n')
      : null;

    // NOTE: Do not fetch/inline the image before starting the SSE stream; that makes the UI look stalled.
    // We'll attach the image inside the stream (and emit status updates) just before the OpenAI call.
    const userContent: string = selectedAssetText ? `${message}\n\n${selectedAssetText}` : message;

    let messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
      {
        role: 'system',
        content: assistantConfig.systemPrompt,
      },
      ...conversationHistory.map(
        (msg: { role: string; content: string }): OpenAI.Chat.ChatCompletionMessageParam => ({
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
        })
      ),
      {
        role: 'user',
        content: userContent,
      },
    ];

    // Prepare streaming response
    const startTime = Date.now();
    let fullResponse = '';
    let tokenCount = 0;
    const mcpCalls: Array<{ tool: string; args: unknown; result: unknown }> = [];
    let imageUrls: string[] = [];

    // Get Sitecore Search tools (optional - gracefully handle if MCP not available)
    let tools: ReturnType<typeof getAllTools> | undefined;
    let marketerMCPClient: Awaited<ReturnType<typeof getMarketerMCPClient>> | undefined;
    try {
      tools = getAllTools();
      
      debugLog('Total tools loaded (Local):', tools?.length || 0);

      // Initialize marketer-mcp client
      try {
        const authCheck = await checkMarketerMCPAuth(userId, applicationId);
        if (!authCheck.authenticated && authCheck.requiresAuth) {
          debugLog('[Marketer MCP] Skipping connect: user not authenticated in Marketplace app.');
          marketerMCPClient = undefined;
        } else {
          marketerMCPClient = await getMarketerMCPClient(userId, applicationId);
        }

        const marketerTools = marketerMCPClient ? marketerMCPClient.getAvailableTools() : [];
        if (marketerMCPClient) {
          debugLog('Marketer-MCP tools loaded:', marketerTools.length, 'tools');
        }

        if (marketerMCPClient && (process.env.MARKETER_MCP_DEBUG === 'true' || process.env.MARKETER_MCP_DEBUG === '1')) {
          try {
            const interesting = new Set([
              'update_content',
              'update_fields_on_content_item',
              'get_content_item_by_id',
              'get_content_item_by_path',
              'update_asset',
              'upload_asset',
            ]);
            const schemaSummary = marketerTools
              .filter((t) => interesting.has(String(t.name)))
              .map((t) => {
                const schema: any = t.inputSchema || {};
                const props = schema?.properties ? Object.keys(schema.properties) : [];
                const required = Array.isArray(schema?.required) ? schema.required : [];
                return {
                  name: t.name,
                  required,
                  properties: props,
                };
              });
            debugLog('[Marketer MCP] Tool schema summary:', JSON.stringify(schemaSummary, null, 2));
          } catch {
            debugLog('[Marketer MCP] Tool schema summary: [unavailable]');
          }
        }
        
        // Combine tools from both MCP servers
        if (tools && marketerTools.length > 0) {
          // Convert marketer tools to OpenAI tool format and add to tools array
          const formattedMarketerTools = marketerTools.map((tool) => ({
            type: 'function' as const,
            function: {
              name: tool.name,
              description: tool.description,
              parameters: tool.inputSchema as any, // Type assertion needed for dynamic schema
            },
          }));
          tools = [...(tools || []), ...formattedMarketerTools] as any;

          // Append Marketer Tools description to the System Prompt
          const marketerToolsDescription = `
            ## Sitecore Marketer MCP Tools
            IMPORTANT: Use these tools for all AUTHORING and EDITING tasks.

          ${marketerTools.map((t, index) => `
          ${index + 1}. ${t.name} - ${t.description}
            - Parameters: ${Object.keys(t.inputSchema.properties || {}).join(', ') || 'None'}
          `).join('')}
                `;

          if (messages[0].role === 'system') {
             messages[0].content += `\n\n${marketerToolsDescription}`;
          }
        }
      } catch (error) {
        console.warn('Marketer-MCP not available, continuing without it:', error);
      }
    } catch (error) {
      console.warn('MCP tools not available, continuing without them:', error);
      tools = undefined;
    }

    // Stream response
    const stream = new ReadableStream({
      async start(controller) {
        try {
          const encoder = new TextEncoder();

          const TOOL_STATUS_LABELS: Record<string, string> = {
            generate_image: 'Generating an image... ',
            generate_asset_url: 'Generating an asset URL...',
            sitecore_get_recommendations: 'Fetching recommendations...',
            sitecore_create_document: 'Creating document...',
            sitecore_update_document: 'Updating document...',
            sitecore_track_event: 'Tracking event...',

            upload_asset: 'Uploading asset...',
            update_asset: 'Updating asset...',

            // Marketer MCP tools (support both older prefixed names and the raw MCP tool names)
            list_sites: 'Listing all sites...',
            get_site_information: 'Getting site information...',
            get_all_pages_by_site: 'Getting all pages...',
            search_site: 'Searching site pages...',
            get_site_id_from_item: 'Getting site ID...',
            list_components: 'Listing components...',
            get_component: 'Getting component details...',
            get_components_on_page: 'Getting page components...',
            get_allowed_components_by_placeholder: 'Getting allowed components...',
            get_components_by_placeholder: 'Getting placeholder components...',

            mcp_marketer_mcp_list_sites: 'Listing all sites...',
            mcp_marketer_mcp_get_site_information: 'Getting site information...',
            mcp_marketer_mcp_get_all_pages_by_site: 'Getting all pages...',
            mcp_marketer_mcp_search_site: 'Searching site pages...',
            mcp_marketer_mcp_get_site_id_from_item: 'Getting site ID...',
            mcp_marketer_mcp_list_components: 'Listing components...',
            mcp_marketer_mcp_get_component: 'Getting component details...',
            mcp_marketer_mcp_get_components_on_page: 'Getting page components...',
            mcp_marketer_mcp_get_allowed_components_by_placeholder: 'Getting allowed components...',
            mcp_marketer_mcp_get_components_by_placeholder: 'Getting placeholder components...',
          };

          const getToolBaseName = (toolName: string): string => {
            return toolName
              .replace(/^mcp_marketer_mcp_/, '')
              .replace(/^mcp_marketer-mcp_/, '');
          };

          const getToolDisplayName = (toolName: string): string => {
            const base = getToolBaseName(toolName);
            return base
              .replace(/[_-]+/g, ' ')
              .replace(/\b\w/g, (c) => c.toUpperCase());
          };

          const emit = (payload: Record<string, unknown>) => {
            try {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
            } catch (err: any) {
              // Ignore errors if the stream is already closed (e.g. client navigated away)
              if (err.code === 'ERR_INVALID_STATE' || err.message?.includes('closed')) {
                // debugLog('Stream closed by client during emit.');
                return;
              }
              console.error('Error emitting to stream:', err);
            }
          };

          const looksLikeActionPromise = (text: string): boolean => {
            if (!text) return false;
            // Heuristic: the assistant is promising to take an action "now/shortly".
            return /(let me|i will|i'll|i am going to|i can|i will now|i'll now).{0,60}(update|create|add|set|populate|insert|publish|configure|proceed|handle this|do that)/i.test(
              text
            );
          };

          const looksLikeToolRequiredAction = (text: string): boolean => {
            if (!text) return false;
            // Narrower heuristic: only warn/force-retry when the assistant promises to mutate XM Cloud or assets.
            // (Image analysis itself does not require tools.)
            const promise = /(let me|i will|i'll|i am going to|i can|i will now|i'll now)\b/i;
            const action = /(update|create|add|set|populate|insert|publish|configure|remove|delete|rename|move|upload)\b/i;
            const target = /(xm\s*cloud|sitecore|page|component|rendering|datasource|data\s*source|field|item|asset|media\s*library|alt\s*text)\b/i;
            return promise.test(text) && action.test(text) && target.test(text);
          };

          const looksLikeXmCloudMutationRequest = (text: string): boolean => {
            if (!text) return false;
            // If the user is explicitly asking to change XM Cloud (page/components/datasources/fields),
            // require at least one tool call so we don't end up with "I'll do that" narration only.
            const action = /(add|insert|create|update|set|populate|publish|remove|delete|configure)\b/i;
            const target = /(xm\s*cloud|sitecore|page|component|rendering|datasource|data\s*source|field|placeholder|headless-main|item)\b/i;
            return action.test(text) && target.test(text);
          };

          // Accumulate tool calls across chunks
          const toolCallAccumulator: Record<number, { id?: string; name?: string; arguments: string }> = {};

          // Per-request cache to avoid re-executing identical tool calls across rounds.
          // This prevents repeated writes when the model is forced to call tools multiple rounds.
          const toolCallResultCache = new Map<string, unknown>();

          const stableStringify = (value: unknown): string => {
            const seen = new WeakSet<object>();
            const normalize = (v: any): any => {
              if (v === null || v === undefined) return v;
              if (typeof v !== 'object') return v;
              if (seen.has(v)) return '[circular]';
              seen.add(v);
              if (Array.isArray(v)) return v.map(normalize);
              const out: Record<string, any> = {};
              for (const key of Object.keys(v).sort()) {
                out[key] = normalize(v[key]);
              }
              return out;
            };
            return JSON.stringify(normalize(value));
          };

          // Run tool(s) for the current accumulated tool call set
          const runToolCalls = async (): Promise<OpenAI.Chat.ChatCompletionToolMessageParam[]> => {
            const toolResults: OpenAI.Chat.ChatCompletionToolMessageParam[] = [];

            const getMarketerToolByName = (name: string): MarketerMCPTool | undefined => {
              try {
                return marketerMCPClient?.getAvailableTools().find((t: MarketerMCPTool) => t.name === name);
              } catch {
                return undefined;
              }
            };

            const normalizeUpdateAssetArgsForMarketerTool = (rawArgs: any): any => {
              const tool = getMarketerToolByName('update_asset');
              const schema: any = tool?.inputSchema || {};
              const properties: string[] = schema?.properties ? Object.keys(schema.properties) : [];

              const assetId =
                rawArgs?.assetId ??
                rawArgs?.asset_id ??
                rawArgs?.assetID ??
                rawArgs?.id;

              const fieldsCandidate = rawArgs?.fields;
              const fields =
                fieldsCandidate && typeof fieldsCandidate === 'object' && !Array.isArray(fieldsCandidate)
                  ? fieldsCandidate
                  : {};

              // Sitecore field names are often case-sensitive. In this project, the correct alt field name is 'Alt'.
              // Prefer writing to fields.Alt so the update actually applies.
              if (typeof rawArgs?.altText === 'string' && rawArgs.altText.trim()) {
                if ((fields as any).Alt === undefined) {
                  (fields as any).Alt = rawArgs.altText;
                }
              }

              // If the tool doesn't accept altText directly, tuck it into fields.
              const acceptsAltText = properties.includes('altText') || properties.includes('alt_text');
              if (!acceptsAltText && typeof rawArgs?.altText === 'string' && rawArgs.altText.trim()) {
                (fields as any).altText = rawArgs.altText;
              }

              const out: any = { ...rawArgs };

              // Ensure fields is present (this tool schema requires it in your env).
              out.fields = fields;

              // Prefer whichever id key the schema actually defines.
              if (properties.includes('assetId')) out.assetId = String(assetId ?? out.assetId ?? '');
              else if (properties.includes('asset_id')) out.asset_id = String(assetId ?? out.asset_id ?? '');
              else if (properties.includes('id')) out.id = String(assetId ?? out.id ?? '');
              else if (assetId) out.assetId = String(assetId);

              // Keep language consistent.
              if (properties.includes('language')) out.language = String(rawArgs?.language ?? out.language ?? '');

              // If tool accepts altText directly, keep it.
              if (acceptsAltText && typeof rawArgs?.altText === 'string') {
                out.altText = rawArgs.altText;
              }

              return out;
            };

            const buildFieldUpdateArgs = (rawArgs: any, fieldUpdateTool: MarketerMCPTool): any => {
              const schema: any = fieldUpdateTool?.inputSchema || {};
              const properties: string[] = schema?.properties ? Object.keys(schema.properties) : [];
              const required: string[] = Array.isArray(schema?.required) ? schema.required : [];

              const updatedFields = rawArgs?.updatedFields;
              const baseArgs: any = { ...rawArgs };

              // Remove keys that are specific to update_content semantics if the target tool doesn't accept them.
              // We'll only delete if the schema indicates it's not supported.
              for (const key of ['updatedFields', 'createNewVersion']) {
                if (!properties.includes(key) && key in baseArgs) {
                  delete baseArgs[key];
                }
              }

              // Decide which property name the field-update tool expects for field values.
              const candidates = ['updatedFields', 'fields', 'dataFields', 'fieldValues'];
              const chosen =
                candidates.find((k) => required.includes(k)) ||
                candidates.find((k) => properties.includes(k)) ||
                'updatedFields';

              return {
                ...baseArgs,
                [chosen]: updatedFields,
              };
            };

            for (const accumulated of Object.values(toolCallAccumulator)) {
              if (!(accumulated.name && accumulated.arguments && accumulated.id)) continue;

              try {
                const args = JSON.parse(accumulated.arguments);
                if (!tools) continue;

                const defaultDomainId = process.env.SITECORE_DOMAIN_ID || '34706982';
                const defaultRfkId = process.env.SITECORE_RFK_ID || 'rfkid_7';

                const debugArgs = JSON.stringify(args, null, 2);
                debugLog(`Executing ${accumulated.name} with args: ${debugArgs}`);

                // Marketer MCP: distinguish between updating an item record/version vs updating field values.
                // If the model tried to update field values via update_content, reroute to update_fields_on_content_item
                // (the tool designed for field writes) when available.
                let effectiveToolName = accumulated.name;
                let effectiveArgs: any = args;
                if (accumulated.name === 'update_content') {
                  const updatedFields = (args as any)?.updatedFields || (args as any)?.fields;
                  const keys = updatedFields && typeof updatedFields === 'object' ? Object.keys(updatedFields) : [];
                  if (!updatedFields || keys.length === 0) {
                    // It is valid to call update_content without fields if other props (like version) are updated,
                    // but usually we expect fields. We'll strict check in the guardrail below if intended for Marketer MCP field updates.
                  } else {
                    debugLog('[Marketer MCP] update_content provided fields keys:', keys);
                    const fieldUpdateTool = getMarketerToolByName('update_fields_on_content_item');
                    if (fieldUpdateTool) {
                      effectiveToolName = 'update_fields_on_content_item';
                      // If 'fields' key is used, map it to 'updatedFields' for the specialized tool if needed
                      const remappedArgs = { ...args };
                      if ((args as any).fields && !(args as any).updatedFields) {
                          remappedArgs.updatedFields = (args as any).fields;
                          delete (remappedArgs as any).fields;
                      }
                      effectiveArgs = buildFieldUpdateArgs(remappedArgs, fieldUpdateTool);
                      debugLog(
                        '[Marketer MCP] Rerouting update_content(fields) -> update_fields_on_content_item to actually update field values.'
                      );
                    } 
                  }
                }

                // Notify client that a tool is running
                const statusToolName = effectiveToolName;
                const toolBaseName = getToolBaseName(statusToolName);
                const toolDisplayName = getToolDisplayName(statusToolName);
                const statusMessage =
                  TOOL_STATUS_LABELS[statusToolName] ||
                  TOOL_STATUS_LABELS[toolBaseName] ||
                  `Running ${toolDisplayName}...`;

                emit({
                  type: 'status',
                  toolName: effectiveToolName,
                  toolBaseName: getToolBaseName(effectiveToolName),
                  toolDisplayName: getToolDisplayName(effectiveToolName),
                  message: statusMessage,
                });

                // Guardrail: if the model calls update_content without updatedFields while trying to change fields,
                // fail fast with guidance to use update_fields_on_content_item.
                if (accumulated.name === 'update_content') {
                  const updatedFields = (args as any)?.updatedFields || (args as any)?.fields;
                  const keys = updatedFields && typeof updatedFields === 'object' ? Object.keys(updatedFields) : [];
                  if (!updatedFields || keys.length === 0) {
                    console.warn('[Marketer MCP] Blocking update_content call without fields');
                    toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify({
                        error:
                          'Update failed: No fields provided. To update content, please provide the "fields" parameter with key-value pairs (e.g., { fields: { title: "New Title" } }).',
                      }),
                    });
                    continue;
                  }
                }

                // Handle image generation locally via OpenAI images API
                if (accumulated.name === 'generate_image') {
                  const imageResult = await openai.images.generate({
                    model: 'dall-e-3',
                    prompt: args.prompt,
                    size: args.size || '1024x1024',
                    n: args.n || 1,
                  });

                  const urls = (imageResult.data ?? []).map((d) => d.url).filter((u): u is string => Boolean(u));
                  imageUrls.push(...urls);

                  emit({ type: 'image', urls, prompt: args.prompt });

                  const formattedResult = { urls, prompt: args.prompt, size: args.size };

                  await prisma.analytics.create({
                    data: {
                      conversationId: conversation.id,
                      eventType: 'mcp_call',
                      eventData: {
                        tool: accumulated.name,
                        args,
                        timestamp: new Date(),
                      },
                    },
                  });

                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(formattedResult),
                  });

                  mcpCalls.push({ tool: accumulated.name, args, result: formattedResult });
                  debugLog(`Tool ${accumulated.name} executed successfully`);
                  continue;
                }

                // Utility: build Edge asset URL locally
                if (accumulated.name === 'generate_asset_url') {
                  
                  const url = buildEdgeAssetUrl({
                    assetId: args.assetId,
                    explicitUrl: args.explicitUrl,
                  });

                  if (!url) {
                    toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify({
                        error:
                          'Unable to build asset URL. Provide at least { path } and configure ENVIRONMENT_HOST (or pass environmentHost).',
                      }),
                    });
                    continue;
                  }

                  const wRaw = args.thumbnailWidth;
                  const w = typeof wRaw === 'number' && Number.isFinite(wRaw) ? wRaw : 100;
                  const thumbUrl = `${url}${url.includes('?') ? '&' : '?'}w=${encodeURIComponent(String(w))}`;

                  const formattedResult = {
                    url,
                    thumbUrl,
                    assetId: args.assetId,
                  };

                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(formattedResult),
                  });

                  mcpCalls.push({ tool: accumulated.name, args, result: formattedResult });
                  debugLog(`Tool ${accumulated.name} executed successfully`);
                  continue;
                }

                // Client Context Tools
                if (accumulated.name === 'get_application_context') {
                  const meta = conversation.metadata as any;
                  const result = applicationContext || meta?.applicationContext || { error: 'Application context not available' };
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }

                if (accumulated.name === 'get_pages_context') {
                  const meta = conversation.metadata as any;
                  const result = pagesContext || meta?.pagesContext || { error: 'Pages context not available' };
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }

                if (accumulated.name === 'get_host_user') {
                  // Fallback to metadata if direct context is missing
                  const meta = conversation.metadata as any;
                  const rawUser = hostUser || meta?.hostUser;
                  
                  let result;
                  if (rawUser) {
                      // Filter for specific fields as requested to provide cleaner context
                      const { given_name, family_name, email } = rawUser;
                      result = { given_name, family_name, email };
                  } else {
                      result = { error: 'Host user information not available' };
                  }

                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }

                if (accumulated.name === 'get_site_context') {
                  const meta = conversation.metadata as any;
                  const result = siteContext || meta?.siteContext || { error: 'Site context not available' };
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }

                if (accumulated.name === 'reload_page_canvas') {
                  emit({ type: 'client_action', action: 'reload_page_canvas' });
                  const result = { success: true, message: 'Reloading page canvas...' };
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }

                if (accumulated.name === 'navigate_to_page') {
                  emit({ type: 'client_action', action: 'navigate_to_page', data: args });
                  const result = { success: true, message: `Navigating to page ${args.itemId}...` };
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify(result),
                  });
                  mcpCalls.push({ tool: accumulated.name, args, result });
                  continue;
                }


                if (accumulated.name === 'get_page_components') {
                  // Resolve context parameters first
                  const reqPageId = (args as any).pageId || currentPageId || '';
                  const language = (args as any).language || 'en';
                   
                  if (!reqPageId) {
                       // We can't proceed without a page ID, locally or remotely (unless remote has its own context, but we shouldn't rely on it)
                       // Actually, let's keep the error throwing inside the try/catch blocks or specific path to maintain consistent behavior
                  }

                  // Check if MCP has the Tool (name is mapped)
                  const mcpToolName = 'get_components_on_page';
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === mcpToolName);

                  if (hasMcpTool) {
                      try {
                          if (!reqPageId) throw new Error('No page ID provided or found in context.');
                          
                          // Call MCP with resolved args to ensure context is passed
                          const mcpArgs = { ...args, pageId: reqPageId, language };
                          const result = await marketerMCPClient!.callTool(mcpToolName, mcpArgs);
                          
                          toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                          mcpCalls.push({ tool: accumulated.name, args, result });
                          continue;
                      } catch (err: any) {
                          const result = { error: err.message || String(err) };
                          toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                          mcpCalls.push({ tool: accumulated.name, args, result });
                          continue;
                      }
                  }

                  // Local Fallback
                  try {
                    
                    if (!reqPageId) {
                         throw new Error('No page ID provided or found in context.');
                    }

                    const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);

                    const componentsResult = await getComponentsOnPage(reqPageId, language, tokenToUse);
                    
                    const result = { components: componentsResult };
                    
                    toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify(result),
                    });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                    
                  } catch (err: any) {
                    const result = { error: err.message || String(err) };
                     toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify(result),
                    });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }


                if (accumulated.name === 'get_allowed_components') {
                  // Check for MCP tool override
                  const mcpToolName = 'get_allowed_components_by_placeholder';
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === mcpToolName);

                  if (hasMcpTool) {
                       try {
                           // Call MCP directly with original args (names match: pageId, placeholderName)
                           const mcpResult = await marketerMCPClient!.callTool(mcpToolName, args);
                           // Format result for toolResults (text)
                           // mcpResult is the content array (CallToolResult.content)
                           const content = Array.isArray(mcpResult) 
                                ? mcpResult.map((c: any) => c.type === 'text' ? c.text : '').join('\n')
                                : JSON.stringify(mcpResult);
                           
                           toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content });
                           mcpCalls.push({ tool: mcpToolName, args, result: content });
                           continue;
                       } catch (mcpErr) {
                           console.error('[get_allowed_components] MCP execution failed, falling back to local.', mcpErr);
                           // Fallthrough to local
                       }
                  }

                  try {
                    const reqPageId = (args as any).pageId || currentPageId;
                    const ph = (args as any).placeholderName;
                    const language = (args as any).language || 'en';
                    
                    if (!reqPageId) throw new Error('No page ID provided.');
                    if (!ph) throw new Error('No placeholder name provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getAllowedComponents(reqPageId, ph, language, tokenToUse);
                    
                    const result = { allowedComponents: resultData };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'get_page') {
                  try {
                    const reqPageId = (args as any).pageId;
                    const language = (args as any).language || 'en';
                    if (!reqPageId) throw new Error('No page ID provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getPage(reqPageId, language, tokenToUse);
                    
                    const result = { page: resultData };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'get_page_html') {
                  try {
                    const reqPageId = (args as any).pageId;
                    const language = (args as any).language || 'en';
                    if (!reqPageId) throw new Error('No page ID provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getPageHtml(reqPageId, language, tokenToUse);
                    // Truncate huge HTML if needed, but usually we want it all for analysis. 
                    // Warning: massive HTML can blow up context window.
                    const result = { html: resultData }; 
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'get_path_by_url') {
                  try {
                    const url = (args as any).url;
                    if (!url) throw new Error('No URL provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getPagePathByUrl(url, tokenToUse);
                    
                    const result = resultData;
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'get_page_template_by_id') {
                  try {
                    const reqTemplateId = (args as any).templateId;
                    const language = (args as any).language || 'en';
                    if (!reqTemplateId) throw new Error('No template ID provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getPageTemplateById(reqTemplateId, tokenToUse, language);
                    
                    const result = { template: resultData };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }



                if (accumulated.name === 'search_site') {
                   // Intercept: Prefer MCP 'search_site' if available
                   const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'search_site');
                   if (hasMcpTool) {
                       // Fall through to MCP generic handler
                   } else {
                      try {
                        const reqSiteName = (args as any).siteName || siteName;
                        const query = (args as any).query;
                        const language = (args as any).language || 'en';
                        
                        if (!reqSiteName) throw new Error('No site name provided or found.');
                        if (!query) throw new Error('No search query provided.');

                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                            
                            const resultData = await searchSite(reqSiteName, query, language, tokenToUse);
                        
                        const result = { results: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      }
                   }
                }


                if (accumulated.name === 'list_components') {
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_components');
                  
                  // The MCP tool strictly requires site_name. If we only have siteName (from local context/SDK), 
                  // we should use the local implementation unless we want to remap.
                  let hasRequiredMcpArgs = (args as any).site_name;

                  // Adaptation: If we have siteName but not site_name, map it so we can use the MCP tool (which is preferred)
                  if (!hasRequiredMcpArgs && (args as any).siteName) {
                      (args as any).site_name = (args as any).siteName;
                      hasRequiredMcpArgs = true;
                      console.log('[list_components] Remapped siteName -> site_name to enable MCP tool usage.');
                  }

                  if (hasMcpTool && hasRequiredMcpArgs) {
                    // fall through to MCP
                  } else {
                      try {
                        const reqSiteName = (args as any).siteName || siteName;
                        if (!reqSiteName) throw new Error('No site name provided or found.');

const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await listComponents(reqSiteName, tokenToUse);
                        
                        const result = { components: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        // Continue here to avoid falling through if local succeeded
                        continue;
                      } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      }
                  }
                }

                if (accumulated.name === 'get_component') {
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'get_component');
                  
                  // The MCP tool strictly requires component_id. If we only have componentName, we must use the local
                  // implementation which can resolve names to IDs.
                  const hasRequiredMcpArgs = (args as any).component_id;
                  
                  if (hasMcpTool && hasRequiredMcpArgs) {
                      // fall through to MCP
                  } else {
                      try {
                        const componentName = (args as any).componentName;
                        const pageId = (args as any).pageId || currentPageId;
                        if (!componentName) throw new Error('No component name provided.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getComponent(componentName, tokenToUse, siteName, pageId);
                        
                        const result = { component: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      }
                  }
                }

                // --- NEW WRITE TOOLS ---


                if (accumulated.name === 'list_sites') {
                  // If Marketer MCP is available and has this tool, let it fall through to the MCP handler
                  // instead of using the local implementation which may be limited.
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_sites');
                  
                  if (hasMcpTool) {
                     // Do not execute local logic; fall through to generic MCP handler at the end of loop
                  } else {
                      try {
                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getSitesList(tokenToUse);
                        
                        const result = { sites: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        // Only continue if we executed the local tool
                        continue;
                      } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      }
                  }
                }


                if (accumulated.name === 'list_site_collections') {
                    const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_site_collections');
                    if (hasMcpTool) {
                        // Fall through to MCP generic handler
                    } else {
                        try {
                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                            const resultData = await listSiteCollections(tokenToUse);
                            const result = { collections: resultData };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        } catch (err: any) {
                            const result = { error: err.message };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        }
                    }
                }

                if (accumulated.name === 'get_favorite_sites') {
                    try {
                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getFavoriteSites(tokenToUse);
                        const result = { favorites: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }


                if (accumulated.name === 'list_languages') {
                    const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_languages');
                    if (hasMcpTool) {
                        // Fall through to MCP generic handler
                    } else {
                        try {
                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                            const resultData = await listLanguages(tokenToUse);
                            const result = { languages: resultData };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        } catch (err: any) {
                            const result = { error: err.message };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        }
                    }
                }

                if (accumulated.name === 'aggregate_page_data') {
                    try {
                        const { siteId, pageId } = args as any;
                        const language = (args as any).language || 'en';
                        if (!siteId || !pageId) throw new Error('Missing siteId or pageId');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await aggregatePageData(siteId, pageId, tokenToUse, language);
                        const result = { data: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'list_jobs') {
                    const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_jobs');
                    if (hasMcpTool) {
                        // Fall through to MCP generic handler
                    } else {
                        try {
                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                            
                            const resultData = await listJobs(tokenToUse);
                            const result = { jobs: resultData };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        } catch (err: any) {
                            const result = { error: err.message };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        }
                    }
                }

                if (accumulated.name === 'search_assets') {
                    try {
                        const { query } = args as any;
                        const language = (args as any).language || 'en';
                        if (!query) throw new Error('Missing query');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await searchAssets(query, tokenToUse, language);
                        console.log('[search_assets] resultData:', JSON.stringify(resultData, null, 2));

                        const result = { assets: resultData };
                        
                        // Extract and emit assets for UI rendering
                        const extractedAssets = extractChatAssetsFromToolResult({ 
                            results: resultData,
                            thumbnailWidth: 300 // Request larger thumbnails for grid display
                        });
                        if (extractedAssets.length > 0) {
                            emit({ type: 'assets', assets: extractedAssets });
                        }

                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'duplicate_page') {
                    try {
                        const { pageId, newName } = args as any;
                        const language = (args as any).language || 'en';

                        if (!pageId || !newName) throw new Error('Missing args');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await duplicatePage(pageId, newName, tokenToUse, language);
                        const result = { success: true, data: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'get_page_preview_url') {
                    try {
                        const { pageId } = args as any;
                        const language = (args as any).language || 'en';

                        if (!pageId) throw new Error('Missing pageId');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getPagePreviewUrl(pageId, tokenToUse, language);
                        const result = { url: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'create_component_datasource') {
                    try {
                        const { name, templateId, locationId } = args as any;
                        const language = (args as any).language || 'en';
                        if (!name || !templateId || !locationId) throw new Error('Missing args');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await createComponentDatasource(name, templateId, locationId, tokenToUse, language);
                        const result = { success: true, data: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'set_component_datasource') {
                    try {
                        const { pageId, componentId, datasourceId } = args as any;
                        const language = (args as any).language || 'en';
                        if (!pageId || !componentId || !datasourceId) throw new Error('Missing args');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await setComponentDatasource(pageId, componentId, datasourceId, tokenToUse, language);
                        const result = { success: true, data: resultData };
                        emit({ type: 'client_action', action: 'reload_page_canvas' });
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'list_page_children') {
                    try {
                        const { itemId, siteId } = args as any;
                        const language = (args as any).language || 'en';
                        if (!itemId) throw new Error('Missing itemId');

                        // Fallback: If siteId missing, try to resolve from page context?
                        // For now, rely on Agent passing it (or existing tool signature that matches SDK requirement)
                        let effectiveSiteId = siteId || (applicationContext as any)?.site?.id;
                        
                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await listPageChildren(itemId, tokenToUse, language, effectiveSiteId);
                        
                        // Check if SDK returned an error object (instead of throwing)
                        if (resultData && (resultData as any).error && (resultData as any).response) {
                             const errObj = (resultData as any).error;
                             const status = errObj.status || errObj.statusCode;
                             console.warn(`[list_page_children] SDK returned error: ${status}`, errObj);
                             if (status === 401 || status === 403) {
                                 throw new Error('Authentication failed: Service/User is unauthorized to view children of this item.');
                             }
                             throw new Error(`Failed to list children: ${errObj.title || status}`);
                        }

                        const result = { children: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }


                if (accumulated.name === 'list_site_templates') {
                    const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'list_site_templates');
                    if (hasMcpTool) {
                        // Fall through to MCP generic handler
                    } else {
                        try {
                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                            
                            const resultData = await listSiteTemplates(tokenToUse);
                            const result = { templates: resultData };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        } catch (err: any) {
                            const result = { error: err.message };
                             toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        }
                    }
                }


                if (accumulated.name === 'get_rendering_hosts') {
                    const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'get_rendering_hosts');
                    if (hasMcpTool) {
                        // Fall through to MCP generic handler
                    } else {
                        try {
                            const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                            
                            const resultData = await getRenderingHosts(tokenToUse);
                            const result = { hosts: resultData };
                            toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        } catch (err: any) {
                            const result = { error: err.message };
                             toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                            mcpCalls.push({ tool: accumulated.name, args, result });
                            continue;
                        }
                    }
                }

                if (accumulated.name === 'list_page_versions') {
                    try {
                        const { pageId } = args as any;
                        const language = (args as any).language || 'en';
                        if (!pageId) throw new Error('Missing pageId');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await retrievePageVersions(pageId, tokenToUse, language);
                        const result = { versions: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'get_condition_templates') {
                    try {
                        const language = (args as any).language || 'en';
                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await getConditionTemplates(tokenToUse, language);
                        const result = { conditions: resultData };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                    }
                    continue;
                }

                if (accumulated.name === 'add_component_on_page') {
                  try {
                    const { pageId, componentName, placeholderName } = args as any;
                    const language = (args as any).language || 'en';
                      // Pass siteName if available for better resolution
                      const effectiveSiteName = (args as any).siteName || siteName;
                      
                      if (!pageId || !componentName || !placeholderName) throw new Error('Missing required arguments.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await addComponentOnPage(pageId, componentName, placeholderName, language, tokenToUse, effectiveSiteName);
                      
                      const result = { success: true, data: resultData };
                      emit({ type: 'client_action', action: 'reload_page_canvas' });
                      toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                      mcpCalls.push({ tool: accumulated.name, args, result });
                    } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'create_page') {
                  
                  // Try to use MCP tool if available
                  const mcpToolName = 'create_page';
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === mcpToolName);

                  if (hasMcpTool) {
                      try {
                          const result = await marketerMCPClient!.callTool(mcpToolName, args);
                          emit({ type: 'client_action', action: 'reload_page_canvas' });
                          toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                          mcpCalls.push({ tool: accumulated.name, args, result });
                          continue;
                      } catch (err: any) {
                           debugLog(`[create_page] MCP tool failed, falling back to local: ${err.message}`);
                           // Fallback to local
                      }
                  }

                  try {
                    let { parentId, templateId, name } = args as any;
                    const language = (args as any).language || 'en';
                    
                    if (!parentId || !name) throw new Error('Missing required arguments: parentId, name.');

                    const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);

                    // Validate templateId
                    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
                    if (!templateId || !uuidRegex.test(templateId)) {
                        console.log(`[create_page] Invalid templateId '${templateId}'. Attempting to find a default template...`);
                        emit({ type: 'status', message: 'Looking for a default page template...' });

                        try {
                                const templates = await listSiteTemplates(tokenToUse);
                                // Handle various response shapes
                                let templateList: any[] = [];
                                if (Array.isArray(templates)) {
                                    templateList = templates;
                                } else if (templates && Array.isArray((templates as any).data)) {
                                    templateList = (templates as any).data;
                                } else if (templates && Array.isArray((templates as any).items)) {
                                    templateList = (templates as any).items;
                                }
                                
                                if (templateList.length > 0) {
                                  // Prefer 'Page' or 'App Route'
                                  const preferred = templateList.find((t: any) => /page|route/i.test(t.name || ''));
                                  const fallback = templateList[0];
                                  const chosen = preferred || fallback;
                                  
                                  if (chosen?.id) {
                                      templateId = chosen.id;
                                      console.log(`[create_page] Found default template: ${chosen.name} (${chosen.id})`);
                                      emit({ type: 'status', message: `Using template: ${chosen.name}` });
                                  }
                                }
                        } catch (err: any) {
                                console.warn('[create_page] Failed to list templates:', err.message);
                        }
                    }

                    if (!templateId || !uuidRegex.test(templateId)) {
                        throw new Error(`Invalid or missing templateId: '${templateId}'. Please request 'list_site_templates' first or provide a valid GUID.`);
                    }

                        const resultData = await createPage(parentId, templateId, name, language, tokenToUse);
                    
                    const result = { success: true, data: resultData };
                    emit({ type: 'client_action', action: 'reload_page_canvas' });
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                if (accumulated.name === 'create_content_item') {
                  try {
                    const { parentId, templateId, name } = args as any;
                    const language = (args as any).language || 'en';
                    
                    if (!parentId || !templateId || !name) throw new Error('Missing required arguments.');

                    const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                    
                    const resultData = await createContentItem({ parentId, templateId, name, language }, tokenToUse);
                    const result = { success: true, data: resultData };
                    emit({ type: 'client_action', action: 'reload_page_canvas' });
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }


                if (accumulated.name === 'update_content') {
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === 'update_content');
                  if (hasMcpTool) {
                      // fall through to MCP
                  } else {
                      try {
                        const { id, fields } = args as any;
                        const language = (args as any).language || 'en';
                        
                        if (!id || !fields) throw new Error('Missing required arguments.');

const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await updateContent({ id, fields, language }, tokenToUse);
                        
                        const result = { success: true, data: resultData };
                        emit({ type: 'client_action', action: 'reload_page_canvas' });
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      } catch (err: any) {
                        const result = { error: err.message };
                        toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                        mcpCalls.push({ tool: accumulated.name, args, result });
                        continue;
                      }
                  }
                }

                if (accumulated.name === 'delete_content') {
                  try {
                    const { itemId } = args as any;
                    
                    if (!itemId) throw new Error('Missing required arguments.');

                        const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);
                        
                        const resultData = await deleteContent(itemId, tokenToUse);
                    
                    const result = { success: true, data: resultData };
                    emit({ type: 'client_action', action: 'reload_page_canvas' });
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  } catch (err: any) {
                    const result = { error: err.message };
                    toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }


                if (accumulated.name === 'list_pages') {
                  // Intercept: Prefer MCP 'get_all_pages_by_site' if available
                  const mcpToolName = 'get_all_pages_by_site';
                  const hasMcpTool = marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === mcpToolName);
                  
                  if (hasMcpTool && siteName) {
                     try {
                         // Check if requested siteId matches current siteId (or wasn't provided, implying current)
                         const reqSiteId = (args as any).siteId;
                         if (!reqSiteId || reqSiteId === siteId) {
                             debugLog('[list_pages] Delegating to MCP tool:', mcpToolName);
                             
                             const mcpResult = await marketerMCPClient!.callTool(mcpToolName, { 
                                 siteName: siteName,
                                 language: (args as any).language || 'en'
                             });
                             
                             // MCP returns an array of content blocks. We want to extract the JSON from the text block.
                             let pagesData = [];
                             if (Array.isArray(mcpResult) && mcpResult[0]?.text) {
                                try {
                                    pagesData = JSON.parse(mcpResult[0].text);
                                } catch (parseErr) {
                                    debugLog('[list_pages] Failed to parse MCP result as JSON', parseErr);
                                }
                             }
                             
                             const result = { pages: pagesData };
                             toolResults.push({ role: 'tool', tool_call_id: accumulated.id, content: JSON.stringify(result) });
                             mcpCalls.push({ tool: accumulated.name, args, result });
                             continue; // Skip local implementation
                         } else {
                             debugLog('[list_pages] Requested siteId does not match context siteName. Falling back to local implementation.');
                         }
                     } catch (mcpErr) {
                         console.warn('[list_pages] MCP tool call failed, traversing to local fallback.', mcpErr);
                     }
                  }

                  try {
                    const reqSiteId = (args as any).siteId || siteId || '';
                    const language = (args as any).language || 'en';
                    
                    debugLog(`[list_pages] Requesting: siteId=${reqSiteId}, language=${language}`);

                    if (!reqSiteId) {
                         throw new Error('No site ID provided or found in context.');
                    }

                    const tokenToUse = await getSmartToken(userId, req, emit, applicationContext);

                    // Try with Token
                    debugLog(`[list_pages] Calling getAllPagesForSite...`);
                    const pagesResult = await getAllPagesForSite(reqSiteId, language, tokenToUse, process.env.ENVIRONMENT_HOST || '');
                    
                    debugLog(`[list_pages] Success. Found ${Array.isArray(pagesResult) ? pagesResult.length : 0} pages.`);
                    
                    const result = { 
                        pages: Array.isArray(pagesResult) ? pagesResult.map((p: any) => ({
                            id: p.id,
                            name: p.name,
                            displayName: p.displayName,
                            path: p.path
                        })) : []
                    };
                    
                    toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify(result),
                    });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                    
                  } catch (err: any) {
                    const result = { error: err.message || String(err) };
                     toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify(result),
                    });
                    mcpCalls.push({ tool: accumulated.name, args, result });
                  }
                  continue;
                }

                // Route to appropriate MCP client based on tool name
                let result;
                const isMarketerTool =
                  marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === effectiveToolName);

                if (isMarketerTool) {
                  // Deduplicate identical Marketer MCP tool calls within this request.
                  // If the model repeats the same call, reuse the cached result.
                  const signature = `${effectiveToolName}:${stableStringify(effectiveArgs)}`;
                  if (toolCallResultCache.has(signature)) {
                    result = toolCallResultCache.get(signature);
                    debugLog(`[Marketer MCP] Deduped repeated tool call: ${effectiveToolName}`);

                    toolResults.push({
                      role: 'tool',
                      tool_call_id: accumulated.id,
                      content: JSON.stringify(result),
                    });

                    mcpCalls.push({ tool: effectiveToolName, args: effectiveArgs, result });
                    continue;
                  }

                  // Special-case: upload_asset via Agent API (raw multipart) instead of the MCP stub
                  // but only when Agent API credentials are configured.
                  if (effectiveToolName === 'upload_asset') {
                    if (!hasAgentApiCredentialsConfigured()) {
                      console.warn(
                        '[Agent API] upload_asset requested but SITECORE_AGENT_API_* credentials are not configured; routing to marketer-mcp.'
                      );
                      result = await marketerMCPClient!.callTool(effectiveToolName, effectiveArgs);
                      try {
                        toolCallResultCache.set(signature, result);
                      } catch {
                        // ignore cache failures
                      }
                    } else {
                      debugLog('Routing upload_asset to Sitecore Agent API (raw multipart)');
                    if (process.env.MARKETER_MCP_DEBUG === 'true' || process.env.MARKETER_MCP_DEBUG === '1') {
                      try {
                        const fp = (effectiveArgs as any)?.filePath;
                        const isUrl = typeof fp === 'string' && /^https?:\/\//i.test(fp);
                        const isData = typeof fp === 'string' && /^data:/i.test(fp);
                        const hasB64 = typeof (effectiveArgs as any)?.fileContentBase64 === 'string';
                        const headerKeys = Object.keys(((effectiveArgs as any)?.downloadHeaders ?? {}) as any);
                        debugLog('[upload_asset] filePath:', fp);
                        debugLog('[upload_asset] pathKind:', { isUrl, isData, hasB64, downloadHeaderKeys: headerKeys });
                      } catch {
                        // ignore debug logging failures
                      }
                    }
                    result = await uploadAssetViaAgentApi(userId, effectiveArgs);
                    try {
                      toolCallResultCache.set(signature, result);
                    } catch {
                      // ignore cache failures
                    }
                    }
                  } else if (effectiveToolName === 'update_asset') {
                    if (!hasAgentApiCredentialsConfigured()) {
                      console.warn(
                        '[Agent API] update_asset requested but SITECORE_AGENT_API_* credentials are not configured; routing to marketer-mcp.'
                      );
                      const normalizedArgs = normalizeUpdateAssetArgsForMarketerTool(effectiveArgs);
                      result = await marketerMCPClient!.callTool(effectiveToolName, normalizedArgs);
                      try {
                        toolCallResultCache.set(signature, result);
                      } catch {
                        // ignore cache failures
                      }
                    } else {
                      debugLog('Routing update_asset to Sitecore Agent API (raw REST)');
                      const assetId =
                        (effectiveArgs as any)?.assetId ||
                        (effectiveArgs as any)?.asset_id ||
                        (effectiveArgs as any)?.assetID;
                      result = await updateAssetViaAgentApi(userId, {
                        assetId: String(assetId ?? ''),
                        language: String((effectiveArgs as any)?.language ?? ''),
                        name: (effectiveArgs as any)?.name,
                        altText: (effectiveArgs as any)?.altText,
                        fields: (effectiveArgs as any)?.fields,
                      });
                      try {
                        toolCallResultCache.set(signature, result);
                      } catch {
                        // ignore cache failures
                      }
                    }
                  } else {

                  debugLog(`Routing ${effectiveToolName} to marketer-mcp`);
                  if (process.env.MARKETER_MCP_DEBUG === 'true' || process.env.MARKETER_MCP_DEBUG === '1') {
                    try {
                      const json = JSON.stringify(effectiveArgs, null, 2);
                      debugLog('[Marketer MCP] Tool args JSON:', json.length > 12000 ? `${json.slice(0, 12000)}…[truncated ${json.length}]` : json);
                    } catch {
                      debugLog('[Marketer MCP] Tool args JSON: [unserializable]');
                    }
                  }
                    result = await marketerMCPClient!.callTool(effectiveToolName, effectiveArgs);

                    try {
                      toolCallResultCache.set(signature, result);
                    } catch {
                      // ignore cache failures
                    }
                  }
                } else {
                  debugLog(`Tool ${accumulated.name} is not recognized as a Marketer MCP tool or local tool.`);
                }

                debugLog(`Result from ${accumulated.name}:`, result);
                mcpCalls.push({ tool: effectiveToolName, args: effectiveArgs, result });

                await prisma.analytics.create({
                  data: {
                    conversationId: conversation.id,
                    eventType: 'mcp_call',
                    eventData: {
                      tool: effectiveToolName,
                      args: effectiveArgs,
                      timestamp: new Date(),
                    },
                  },
                });

                toolResults.push({
                  role: 'tool',
                  tool_call_id: accumulated.id,
                  content: JSON.stringify(result),
                });

                debugLog(`Tool ${accumulated.name} executed successfully`);
              } catch (error) {
                console.error('MCP tool call error:', error);
                if (accumulated.id) {
                  toolResults.push({
                    role: 'tool',
                    tool_call_id: accumulated.id,
                    content: JSON.stringify({ error: String(error) }),
                  });
                }
              }
            }

            // Clear accumulator for next round
            for (const key of Object.keys(toolCallAccumulator)) {
              delete toolCallAccumulator[Number(key)];
            }

            return toolResults;
          };

          let currentMessages: OpenAI.Chat.ChatCompletionMessageParam[] = messages;

          // Attach selected image inside the stream so the UI can show progress while we fetch/inline it.
          if (assetUrl) {
            const imagePrepStart = Date.now();
            emit({ type: 'status', message: 'Loading selected image for analysis...' });

            // Request a resized image for faster transfer + vision processing.
            const resizedAssetUrl = withSearchParam(assetUrl, 'w', '1024');
            const inlineImageUrl = await tryFetchImageAsDataUrl(resizedAssetUrl);
            const imageUrlForModel = inlineImageUrl ?? resizedAssetUrl;

            const prepMs = Date.now() - imagePrepStart;
            if (prepMs > 500) {
              emit({
                type: 'status',
                message: inlineImageUrl
                  ? `Selected image loaded (${prepMs}ms)`
                  : `Using image URL for analysis (${prepMs}ms)`,
              });
            }

            // Replace the last user message content with multi-part (text + image).
            const last = currentMessages[currentMessages.length - 1];
            if (last && last.role === 'user') {
              const baseText = typeof last.content === 'string' ? last.content : userContent;
              currentMessages = [
                ...currentMessages.slice(0, -1),
                {
                  role: 'user',
                  content: [
                    { type: 'text', text: baseText },
                    { type: 'image_url', image_url: { url: imageUrlForModel } },
                  ],
                },
              ];

              // Encourage a single-pass answer (avoid "please hold on" without output).
              currentMessages = [
                ...currentMessages,
                {
                  role: 'system',
                  content:
                    'An image is attached. Provide the image description and proposed alt text immediately in this response. Do not say you will analyze it later; just do it now.',
                },
              ];
            }
          }
          let completed = false;
          let rounds = 0;

          let forceToolCallNextRound = false;
          let forcedToolRetryUsed = false;

          // Track tool names the model *requested* (even if not executed).
          // This helps debug cases where the model indicates tool use but later fails to run tools.
          const requestedToolNames = new Set<string>();

          while (!completed && rounds < 6) {
            rounds += 1;

            // Only force tool usage until we have at least one successful tool call.
            // Otherwise, the model can get stuck calling tools every round (up to 6).
            const requireToolsThisRound = forceToolCallNextRound;
            forceToolCallNextRound = false;

            const shouldRequireToolCall =
              Array.isArray(tools) &&
              tools.length > 0 &&
              (requireToolsThisRound ||
                (intentResult?.assistantType === 'content_authoring' &&
                  looksLikeXmCloudMutationRequest(message) &&
                  mcpCalls.length === 0));

            const completion = await openai.chat.completions.create({
              model: 'gpt-4o',
              messages: currentMessages,
              tools,
              // Some OpenAI SDK typings don't include 'required'; cast to avoid type friction.
              tool_choice: (shouldRequireToolCall ? 'required' : 'auto') as any,
              stream: true,
              temperature: 0.7,
            });
          
            let finishReason: string | null | undefined;

            for await (const chunk of completion) {
              const delta = chunk.choices[0]?.delta;

              if (delta?.tool_calls) {
                for (const toolCall of delta.tool_calls) {
                  const index = toolCall.index ?? 0;

                  if (!toolCallAccumulator[index]) {
                    toolCallAccumulator[index] = { arguments: '' };
                  }

                  if (toolCall.id) {
                    toolCallAccumulator[index].id = toolCall.id;
                  }

                  if (toolCall.function?.name) {
                    toolCallAccumulator[index].name = toolCall.function.name;

                    // Log immediately when the model starts emitting a tool name, but only once per name.
                    // The user asked for logging when intent isn't empty.
                    if (intentResult?.assistantType && !requestedToolNames.has(toolCall.function.name)) {
                      requestedToolNames.add(toolCall.function.name);
                      debugLog('[Tool request]', {
                        intent: intentResult.assistantType,
                        tool: toolCall.function.name,
                        toolCallId: toolCall.id,
                        round: rounds,
                        conversationId: conversation?.id,
                      });
                    }
                  }

                  if (toolCall.function?.arguments) {
                    toolCallAccumulator[index].arguments += toolCall.function.arguments;
                  }
                }
              }

              if (delta?.content) {
                fullResponse += delta.content;
                tokenCount++;
                emit({ type: 'content', content: delta.content });
              }

              if (chunk.choices[0]?.finish_reason) {
                finishReason = chunk.choices[0].finish_reason;
              }
            }

            if (finishReason === 'tool_calls') {
              debugLog('Tool calls complete, executing...');

              const assistantMessage: OpenAI.Chat.ChatCompletionAssistantMessageParam = {
                role: 'assistant',
                content: null,
                tool_calls: Object.values(toolCallAccumulator).map((tc) => ({
                  id: tc.id!,
                  type: 'function' as const,
                  function: {
                    name: tc.name!,
                    arguments: tc.arguments,
                  },
                })),
              };

              const toolResults = await runToolCalls();

              if (toolResults.length === 0) {
                // No tool results means we can't progress; avoid hanging.
                emit({
                  type: 'content',
                  content: '\n\nI attempted to run a tool, but did not receive any results. Please try again.',
                });
                completed = true;
                break;
              }

              currentMessages = [...currentMessages, assistantMessage, ...toolResults];
              continue;
            }

            if (finishReason === 'stop') {
              // If the assistant claims it will take an XM Cloud action but didn't emit tool_calls,
              // do one forced retry that requires tools (prevents "I'll do that now" without execution).
              const interimClean = cleanIncompleteMarkdown(fullResponse);
              const shouldForceRetry =
                !forcedToolRetryUsed &&
                Array.isArray(tools) &&
                tools.length > 0 &&
                (intentResult?.assistantType === 'content_authoring' || intentResult?.assistantType === 'asset_manager') &&
                looksLikeToolRequiredAction(interimClean) &&
                mcpCalls.length === 0;

              if (shouldForceRetry) {
                forcedToolRetryUsed = true;
                forceToolCallNextRound = true;

                currentMessages = [
                  ...currentMessages,
                  { role: 'assistant', content: interimClean },
                  {
                    role: 'system',
                    content:
                      'You described an XM Cloud action. Now invoke the appropriate MCP tools to perform it. Call tools; do not respond with prose.',
                  },
                ];

                // Continue the loop to allow tool_calls to occur.
                continue;
              }

              completed = true;
              break;
            }

            // If we get here, something unexpected happened (length, content_filter, etc.)
            completed = true;
          }

          // Persist + finalize stream
          const latency = Date.now() - startTime;

          const cleanedResponse = cleanIncompleteMarkdown(fullResponse);

          // If the assistant seems to be promising an action but no tools ran, emit a warning so the UI doesn't
          // look like it "stalled" or silently dropped an intended action.
          const promisedActionButNoTools = looksLikeToolRequiredAction(cleanedResponse) && mcpCalls.length === 0;
          if (promisedActionButNoTools) {
            emit({
              type: 'warning',
              message:
                'The assistant described an action, but no tools were invoked. If you intended an XM Cloud update, retry or ask it to run the MCP tools explicitly.',
            });
          }

          await prisma.message.create({
            data: {
              conversationId: conversation.id,
              role: 'assistant',
              content: cleanedResponse,
              images: imageUrls,
              currentPageId,
              tokens: tokenCount,
              latencyMs: latency,
              // Prisma Json input types are strict; mcpCalls contains unknown values.
              // This is safe at runtime (JSON-serializable) and intended for debugging/analytics.
              mcpCalls: {
                calls: JSON.parse(JSON.stringify(mcpCalls)),
                promisedActionButNoTools,
              } as any,
            },
          });

          await prisma.analytics.create({
            data: {
              conversationId: conversation.id,
              eventType: 'token_usage',
              eventData: {
                tokens: tokenCount,
                latencyMs: latency,
              },
            },
          });

          const messageCount = await prisma.message.count({
            where: { conversationId: conversation.id },
          });

          if (messageCount === 2 && !conversation.title) {
            const title = await generateConversationTitle([
              { role: 'user', content: message },
              { role: 'assistant', content: cleanedResponse },
            ]);

            await prisma.conversation.update({
              where: { id: conversation.id },
              data: { title },
            });

            emit({ type: 'title', title });
          }

          if (intentResult.shouldSwitch) {
            emit({
              type: 'assistant_switch',
              newAssistant: intentResult.assistantType,
              confidence: intentResult.confidence,
            });
          }

          // emit({ type: 'done', conversationId: conversation.id });
          try {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', conversationId: conversation.id })}\n\n`));
            controller.close();
          } catch (err: any) {
             // Ignore "Controller is already closed" errors which happen if client disconnects early
          }
        } catch (error) {
          console.error('Streaming error:', error);
          try {
            const encoder = new TextEncoder();
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({
                  type: 'error',
                  message: 'Streaming error',
                  details: error instanceof Error ? error.message : String(error),
                })}\n\n`
              )
            );
          } catch {
            // ignore
          }
           try {
            controller.close();
          } catch (err: any) {
             // Ignore "Controller is already closed" errors
             if (err.code !== 'ERR_INVALID_STATE') {
                 // ignore
             }
          }
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Chat API error:', error);
    if (isDatabaseUnavailableError(error)) {
      return NextResponse.json(
        {
          error: 'Database unavailable',
          code: 'DB_UNAVAILABLE',
          message: getDatabaseUnavailableHint(),
        },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// Get conversation history
export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const userId = searchParams.get('userId');
    const siteId = searchParams.get('siteId');
    const conversationId = searchParams.get('conversationId');

    if (conversationId) {
      // Get specific conversation
      const conversation = await prisma.conversation.findUnique({
        where: { id: conversationId },
        include: {
          messages: { orderBy: { timestamp: 'asc' } },
        },
      });

      return NextResponse.json({ conversation });
    }

    if (!userId || !siteId) {
      return NextResponse.json(
        { error: 'Missing userId or siteId' },
        { status: 400 }
      );
    }

    // Get all conversations for user and site
    const conversations = await prisma.conversation.findMany({
      where: { userId, siteId },
      include: {
        messages: {
          orderBy: { timestamp: 'asc' },
          take: 1, // Just first message for preview
        },
      },
      orderBy: { updatedAt: 'desc' },
    });

    return NextResponse.json({ conversations });
  } catch (error) {
    console.error('Get conversations error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

// Delete a conversation
export async function DELETE(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const conversationId = searchParams.get('conversationId');
    const userId = searchParams.get('userId');
    const siteId = searchParams.get('siteId');

    if (!conversationId) {
      return NextResponse.json(
        { error: 'Missing conversationId' },
        { status: 400 }
      );
    }

    const conversation = await prisma.conversation.findFirst({
      where: {
        id: conversationId,
        ...(userId ? { userId } : {}),
        ...(siteId ? { siteId } : {}),
      },
    });

    if (!conversation) {
      return NextResponse.json(
        { error: 'Conversation not found' },
        { status: 404 }
      );
    }

    await prisma.conversation.delete({ where: { id: conversationId } });

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Delete conversation error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
