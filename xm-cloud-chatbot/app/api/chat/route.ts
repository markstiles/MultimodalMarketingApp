import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';
import { prisma } from '@/lib/db';
import { getMCPClient } from '@/lib/mcp/search-client';
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
    try {
      tools = getAllTools();
      console.log('Tools loaded:', tools?.length || 0, 'tools');
    } catch (error) {
      console.warn('MCP tools not available, continuing without them:', error);
      tools = undefined;
    }

    // Stream response
    const stream = new ReadableStream({
      async start(controller) {
        try {
          const completion = await openai.chat.completions.create({
            model: 'gpt-4-turbo',
            messages,
            tools,
            stream: true,
            temperature: 0.7,
          });
          
          const encoder = new TextEncoder();
          
          // Accumulate tool calls across chunks
          const toolCallAccumulator: Record<number, { id?: string; name?: string; arguments: string }> = {};

          const TOOL_STATUS_LABELS: Record<string, string> = {
            generate_image: 'Generating an image... ',
            sitecore_search_query: 'Searching content...',
            sitecore_search_with_facets: 'Running faceted search...',
            sitecore_ai_search: 'Running AI search...',
            sitecore_get_recommendations: 'Fetching recommendations...',
            sitecore_create_document: 'Creating document...',
            sitecore_update_document: 'Updating document...',
            sitecore_track_event: 'Tracking event...',
          };
          
          for await (const chunk of completion) {
            //console.log('Received chunk:', chunk);
            const delta = chunk.choices[0]?.delta;

            // Handle tool calls (accumulate arguments across chunks)
            if (delta?.tool_calls) {
              //console.log('Processing tool calls in chunk:', delta.tool_calls);
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
            
            // Execute accumulated tool calls when streaming finishes
            if (chunk.choices[0]?.finish_reason === 'tool_calls') {
              console.log('Tool calls complete, executing...');
              const toolResults: OpenAI.Chat.ChatCompletionToolMessageParam[] = [];
              
              for (const accumulated of Object.values(toolCallAccumulator)) {
                if (accumulated.name && accumulated.arguments && accumulated.id) {
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
                    const statusPayload = JSON.stringify({
                      type: 'status',
                      message: TOOL_STATUS_LABELS[accumulated.name] || 'Running a tool...'
                    });
                    controller.enqueue(encoder.encode(`data: ${statusPayload}\n\n`));

                    // Handle image generation locally via OpenAI images API
                    if (accumulated.name === 'generate_image') {
                      const imageResult = await openai.images.generate({
                        //model: 'gpt-image-1',
                        model: 'dall-e-3',
                        prompt: args.prompt,
                        size: args.size || '1024x1024',
                        n: args.n || 1,
                      });

                      const urls = (imageResult.data ?? [])
                        .map((d) => d.url)
                        .filter((u): u is string => Boolean(u));

                      // Store image URLs for database persistence
                      imageUrls.push(...urls);

                      // Emit SSE event to client with image URLs
                      const imagePayload = JSON.stringify({
                        type: 'image',
                        urls,
                        prompt: args.prompt,
                      });
                      controller.enqueue(encoder.encode(`data: ${imagePayload}\n\n`));

                      const formattedResult = { urls, prompt: args.prompt, size: args.size };

                      // Track analytics
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

                      // Add tool result to feed back into the model
                      toolResults.push({
                        role: 'tool',
                        tool_call_id: accumulated.id,
                        content: JSON.stringify(formattedResult),
                      });

                      mcpCalls.push({ tool: accumulated.name, args, result: formattedResult });
                      console.log(`Tool ${accumulated.name} executed successfully`);
                    } else {
                      // Default: execute via MCP client
                      const mcpClient = await getMCPClient();
                      const result = await mcpClient.callTool(accumulated.name, args);
                      console.log(`Result from ${accumulated.name}:`, result);
                      mcpCalls.push({
                        tool: accumulated.name,
                        args,
                        result,
                      });

                      // Track MCP call in analytics
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
                      
                      // Add tool result to be sent back to model
                      toolResults.push({
                        role: 'tool',
                        tool_call_id: accumulated.id,
                        content: JSON.stringify(result),
                      });
                      
                      console.log(`Tool ${accumulated.name} executed successfully`);
                    }
                  } catch (error) {
                    console.error('MCP tool call error:', error);
                    // Add error result
                    if (accumulated.id) {
                      toolResults.push({
                        role: 'tool',
                        tool_call_id: accumulated.id,
                        content: JSON.stringify({ error: String(error) }),
                      });
                    }
                  }
                }
              }
              
              // Call model again with tool results to get synthesis
              if (toolResults.length > 0) {
                console.log('Calling model with tool results...');
                
                // Build assistant message with tool calls
                const assistantMessage: OpenAI.Chat.ChatCompletionAssistantMessageParam = {
                  role: 'assistant',
                  content: null,
                  tool_calls: Object.values(toolCallAccumulator).map((tc, idx) => ({
                    id: tc.id!,
                    type: 'function' as const,
                    function: {
                      name: tc.name!,
                      arguments: tc.arguments,
                    },
                  })),
                };
                
                // Create new message array with tool results
                const messagesWithTools = [
                  ...messages,
                  assistantMessage,
                  ...toolResults,
                ];
                
                // Call model again to synthesize response
                const synthesisCompletion = await openai.chat.completions.create({
                  model: 'gpt-4-turbo',
                  messages: messagesWithTools,
                  tools,
                  stream: true,
                  temperature: 0.7,
                });
                
                // Stream the synthesis response
                for await (const synthesisChunk of synthesisCompletion) {
                  const synthesisDelta = synthesisChunk.choices[0]?.delta;
                  
                  if (synthesisDelta?.content) {
                    fullResponse += synthesisDelta.content;
                    tokenCount++;

                    // Send chunk to client
                    const data = JSON.stringify({
                      type: 'content',
                      content: synthesisDelta.content,
                    });
                    controller.enqueue(encoder.encode(`data: ${data}\n\n`));
                  }
                  
                  // Handle finish of synthesis
                  if (synthesisChunk.choices[0]?.finish_reason === 'stop') {
                    const latency = Date.now() - startTime;

                    // Clean up any incomplete markdown before saving
                    const cleanedResponse = cleanIncompleteMarkdown(fullResponse);

                    // Save assistant message
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

                    // Track token usage
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

                    // Generate title after 2nd message
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

                      // Send title update to client
                      const titleData = JSON.stringify({
                        type: 'title',
                        title,
                      });
                      controller.enqueue(encoder.encode(`data: ${titleData}\n\n`));
                    }

                    // Send assistant switch notification if applicable
                    if (intentResult.shouldSwitch) {
                      const switchData = JSON.stringify({
                        type: 'assistant_switch',
                        newAssistant: intentResult.assistantType,
                        confidence: intentResult.confidence,
                      });
                      controller.enqueue(encoder.encode(`data: ${switchData}\n\n`));
                    }

                    // Send completion
                    const doneData = JSON.stringify({
                      type: 'done',
                      conversationId: conversation.id,
                    });
                    controller.enqueue(encoder.encode(`data: ${doneData}\n\n`));
                  }
                }
              }
            }

            // Handle content
            if (delta?.content) {
              fullResponse += delta.content;
              tokenCount++;

              // Send chunk to client
              const data = JSON.stringify({
                type: 'content',
                content: delta.content,
              });
              controller.enqueue(encoder.encode(`data: ${data}\n\n`));
            }

            // Handle finish
            if (chunk.choices[0]?.finish_reason === 'stop') {
              const latency = Date.now() - startTime;

              // Clean up any incomplete markdown before saving
              const cleanedResponse = cleanIncompleteMarkdown(fullResponse);

              // Save assistant message
              await prisma.message.create({
                data: {
                  conversationId: conversation.id,
                  role: 'assistant',
                  content: cleanedResponse,
                  images: imageUrls,
                  currentPageId,
                  tokens: tokenCount,
                  //mcpCalls: mcpCalls,
                  latencyMs: latency,
                },
              });

              // Track token usage
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

              // Generate title after 2nd message (1st user + 1st assistant)
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

                // Send title update to client
                const titleData = JSON.stringify({
                  type: 'title',
                  title,
                });
                controller.enqueue(encoder.encode(`data: ${titleData}\n\n`));
              }

              // Send assistant switch notification if applicable
              if (intentResult.shouldSwitch) {
                const switchData = JSON.stringify({
                  type: 'assistant_switch',
                  newAssistant: intentResult.assistantType,
                  confidence: intentResult.confidence,
                });
                controller.enqueue(encoder.encode(`data: ${switchData}\n\n`));
              }

              // Send completion
              const doneData = JSON.stringify({
                type: 'done',
                conversationId: conversation.id,
              });
              controller.enqueue(encoder.encode(`data: ${doneData}\n\n`));
            }
          }

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
