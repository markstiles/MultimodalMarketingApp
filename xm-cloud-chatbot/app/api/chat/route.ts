import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { prisma } from '@/lib/db';
import { getMCPClient } from '@/lib/mcp/search-client';
import { getMarketerMCPClient, checkMarketerMCPAuth, MarketerMCPTool } from '@/lib/mcp/marketer-client';
import { getAllTools } from '@/lib/mcp/tools';
import { getAssistantConfig } from '@/lib/prompts/templates';
import { classifyIntent } from '@/lib/utils/classify-intent';
import { generateConversationTitle } from '@/lib/utils/generate-title';
import { AssistantType } from '@/lib/types/assistant';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

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
    } = body;

    if (!message || !userId || !siteId) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Check if user is authenticated for marketer-mcp
    const authStatus = await checkMarketerMCPAuth(userId);
    if (authStatus.requiresAuth) {
      return NextResponse.json(
        {
          error: 'Authentication required',
          requiresAuth: true,
          authUrl: `/api/auth/login?userId=${encodeURIComponent(userId)}&redirectUri=${encodeURIComponent('/editor-panel')}`,
        },
        { status: 401 }
      );
    }

    // Get or create conversation
    let conversation = conversationId
      ? await prisma.conversation.findUnique({
          where: { id: conversationId },
          include: { messages: { orderBy: { timestamp: 'asc' } } },
        })
      : null;
    console.log('Conversation fetched:', conversation?.id || 'new conversation');

    // Get conversation history
    const conversationHistory = conversation?.messages.map((m: { role: string; content: string }) => ({
      role: m.role,
      content: m.content,
    })) || [];
    console.log('Conversation history length:', conversationHistory.length);

    // Classify intent (initial or reclassification)
    const intentResult = await classifyIntent(
      message,
      conversationHistory.length > 0 ? conversationHistory : undefined,
      conversation?.assistantType as AssistantType | undefined
    );
    console.log('Intent classification result:', intentResult);

    // Create new conversation if needed
    if (!conversation) {
      conversation = await prisma.conversation.create({
        data: {
          userId,
          siteId,
          assistantType: intentResult.assistantType,
          metadata: { currentPageId },
        },
        include: { messages: true },
      });
    } else if (intentResult.shouldSwitch) {
      // Update conversation assistant type if switching
      conversation = await prisma.conversation.update({
        where: { id: conversation.id },
        data: { assistantType: intentResult.assistantType },
        include: { messages: { orderBy: { timestamp: 'asc' } } },
      });

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
    const assistantConfig = getAssistantConfig(
      conversation.assistantType as AssistantType
    );

    // Prepare messages for OpenAI
    const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
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
        content: message,
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
      console.log('Search tools loaded:', tools?.length || 0, 'tools');
      
      // Initialize marketer-mcp client
      try {
        marketerMCPClient = await getMarketerMCPClient(userId);
        const marketerTools = marketerMCPClient.getAvailableTools();
        console.log('Marketer-MCP tools loaded:', marketerTools.length, 'tools');
        
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
            sitecore_search_query: 'Searching content...',
            sitecore_search_with_facets: 'Running faceted search...',
            sitecore_ai_search: 'Running AI search...',
            sitecore_get_recommendations: 'Fetching recommendations...',
            sitecore_create_document: 'Creating document...',
            sitecore_update_document: 'Updating document...',
            sitecore_track_event: 'Tracking event...',

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
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
          };

          // Accumulate tool calls across chunks
          const toolCallAccumulator: Record<number, { id?: string; name?: string; arguments: string }> = {};

          // Run tool(s) for the current accumulated tool call set
          const runToolCalls = async (): Promise<OpenAI.Chat.ChatCompletionToolMessageParam[]> => {
            const toolResults: OpenAI.Chat.ChatCompletionToolMessageParam[] = [];

            for (const accumulated of Object.values(toolCallAccumulator)) {
              if (!(accumulated.name && accumulated.arguments && accumulated.id)) continue;

              try {
                const args = JSON.parse(accumulated.arguments);
                if (!tools) continue;

                const defaultDomainId = process.env.SITECORE_DOMAIN_ID || '34706982';
                const defaultRfkId = process.env.SITECORE_RFK_ID || 'rfkid_7';

                // Ensure required fields and defaults for Sitecore search tools
                if (
                  accumulated.name === 'sitecore_search_query' ||
                  accumulated.name === 'sitecore_search_with_facets' ||
                  accumulated.name === 'sitecore_ai_search'
                ) {
                  if (!args.fields) {
                    args.fields = ['name', 'description'];
                  }
                  if (!args.domainId) {
                    args.domainId = defaultDomainId;
                  }
                  if (!args.rfkId) {
                    args.rfkId = defaultRfkId;
                  }
                  if (!args.entity || args.entity === 'page') {
                    args.entity = 'content';
                  }
                  if (!args.page) {
                    args.page = 1;
                  }
                  if (!args.limit) {
                    args.limit = 10;
                  }
                  if (!args.keyphrase) {
                    args.keyphrase = '*';
                  }

                  // Apply site filter if siteId is available
                  if (siteId) {
                    const siteFilter = {
                      type: 'eq',
                      name: 'site',
                      values: [String(siteId)],
                    };

                    if (Array.isArray(args.filter)) {
                      args.filter = [...args.filter, siteFilter];
                    } else if (Array.isArray(args.filters)) {
                      args.filters = [...args.filters, siteFilter];
                    } else {
                      // Prefer 'filters' key if absent
                      args.filters = [siteFilter];
                    }
                  }
                }

                const debugArgs = JSON.stringify(args, null, 2);
                console.log(`Executing ${accumulated.name} with args: ${debugArgs}`);

                // Notify client that a tool is running
                const toolName = accumulated.name;
                const toolBaseName = getToolBaseName(toolName);
                const toolDisplayName = getToolDisplayName(toolName);
                const statusMessage =
                  TOOL_STATUS_LABELS[toolName] ||
                  TOOL_STATUS_LABELS[toolBaseName] ||
                  `Running ${toolDisplayName}...`;

                emit({
                  type: 'status',
                  toolName,
                  toolBaseName,
                  toolDisplayName,
                  message: statusMessage,
                });

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
                  console.log(`Tool ${accumulated.name} executed successfully`);
                  continue;
                }

                // Route to appropriate MCP client based on tool name
                let result;
                const isMarketerTool =
                  marketerMCPClient && marketerMCPClient.getAvailableTools().some((t: MarketerMCPTool) => t.name === accumulated.name);

                if (isMarketerTool) {
                  console.log(`Routing ${accumulated.name} to marketer-mcp`);
                  result = await marketerMCPClient!.callTool(accumulated.name, args);
                } else {
                  console.log(`Routing ${accumulated.name} to search-mcp`);
                  const mcpClient = await getMCPClient();
                  result = await mcpClient.callTool(accumulated.name, args);
                }

                console.log(`Result from ${accumulated.name}:`, result);
                mcpCalls.push({ tool: accumulated.name, args, result });

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
                  content: JSON.stringify(result),
                });

                console.log(`Tool ${accumulated.name} executed successfully`);
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
          let completed = false;
          let rounds = 0;

          while (!completed && rounds < 6) {
            rounds += 1;
            const completion = await openai.chat.completions.create({
              model: 'gpt-4-turbo',
              messages: currentMessages,
              tools,
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
              console.log('Tool calls complete, executing...');

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
              completed = true;
              break;
            }

            // If we get here, something unexpected happened (length, content_filter, etc.)
            completed = true;
          }

          // Persist + finalize stream
          const latency = Date.now() - startTime;

          // If the model didn't emit any assistant content but tools ran,
          // stream a basic summary so the UI still shows an answer.
          if (!fullResponse.trim() && mcpCalls.length > 0) {
            const fallback =
              'Here are the tool results:\n\n' +
              mcpCalls
                .map((c) => {
                  const args = JSON.stringify(c.args ?? {}, null, 2);
                  const result = JSON.stringify(c.result ?? {}, null, 2);
                  return `### ${c.tool}\n\n**Args**\n\n\`\`\`json\n${args}\n\`\`\`\n\n**Result**\n\n\`\`\`json\n${result}\n\`\`\``;
                })
                .join('\n\n');

            fullResponse = fallback;
            emit({ type: 'content', content: fallback });
          }

          const cleanedResponse = cleanIncompleteMarkdown(fullResponse);

          await prisma.message.create({
            data: {
              conversationId: conversation.id,
              role: 'assistant',
              content: cleanedResponse,
              images: imageUrls,
              currentPageId,
              tokens: tokenCount,
              latencyMs: latency,
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

          emit({ type: 'done', conversationId: conversation.id });
          controller.close();
        } catch (error) {
          console.error('Streaming error:', error);
          controller.error(error);
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
