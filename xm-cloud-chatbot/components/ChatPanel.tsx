'use client';

import { useState, useRef, useEffect } from 'react';
import { MediaAssetContext } from '@/lib/types/editor-messages';
import { AssistantType } from '@/lib/types/assistant';
import { getDefaultAssistantType } from '@/lib/prompts/templates';
import MessageBubble from '@/components/MessageBubble';
import AssistantBadge from '@/components/AssistantBadge';
import ConversationHistory from '@/components/ConversationHistory';
import toast, { Toaster } from 'react-hot-toast';
import { checkAuthStatus } from '@/lib/utils/auth-helpers';
import { clearChatRecovery, loadChatRecovery, saveChatRecovery } from '@/lib/utils/chat-recovery';
import type { ApplicationContext, PagesContext, UserInfo } from '@sitecore-marketplace-sdk/client';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  assets?: Array<{
    kind: 'image' | 'file';
    url: string;
    thumbUrl?: string;
    name?: string;
    itemId?: string;
    path?: string;
    extension?: string;
    size?: number;
    description?: string;
    width?: number;
    height?: number;
    altText?: string;
  }>;
  timestamp?: Date;
}

interface ChatPanelProps {
  applicationContext?: ApplicationContext;
  pagesContext?: PagesContext;
  siteContext?: any;
  user?: UserInfo;
  environmentHost?: string;
  selectedAsset?: MediaAssetContext;
  selectedComponentId?: string;
  onSendToEditor: (message: unknown) => void;
  onReloadCanvas?: () => void;
  onNavigateToPage?: (itemId: string) => void;
  onExecuteMutation?: (mutation: string, payload?: any) => void;
}

// Filter out markdown image syntax since images are displayed separately
function filterStreamContent(content: string): string {
  return content
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '') // Remove complete markdown images ![alt](url)
    .replace(/!\[([^\]]*)\]\([^)]*$/g, '')  // Remove incomplete markdown images ![alt](url...
    .replace(/!\[([^\]]*)\]$/g, '')          // Remove incomplete markdown images ![alt]
    .replace(/!\[[^\]]*$/g, '')              // Remove incomplete markdown images ![alt...
    .trim();
}

export default function ChatPanel({
  applicationContext,
  pagesContext,
  siteContext,
  user,
  environmentHost,
  selectedAsset,
  selectedComponentId,
  onSendToEditor: _onSendToEditor,
  onReloadCanvas,
  onNavigateToPage,
  onExecuteMutation,
}: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [assistantType, setAssistantType] = useState<AssistantType>(getDefaultAssistantType());
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const resumingFromAuthRef = useRef(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(true); // Default to true to prevent flashing

  // Refs to access latest state in event listeners without dependency cycles
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  // We need a ref for sendMessage to call it from existing useEffect safely
  // but sendMessage is defined below. We'll set this ref in a separate small useEffect
  // or define sendMessage before the main useEffect (which requires moving the effect down).
  const sendMessageRef = useRef<((text: string, options?: { appendUserMessage?: boolean }) => Promise<void>) | null>(null);

  // Listen for popup auth success messages
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
        if (event.data?.type === 'AUTH_SUCCESS') {
            toast.dismiss(); // dismiss all toasts (including the login prompt)
            toast.success('Authentication successful!');
            resumingFromAuthRef.current = true;

            // Automatically retry the last user message
            const currentMessages = messagesRef.current || [];
            const lastUserMessage = [...currentMessages].reverse().find(m => m.role === 'user');
            
            if (lastUserMessage && sendMessageRef.current) {
                console.log('Resuming conversation with last user message:', lastUserMessage.content);
                // We re-append the message to make it clear a new request is happening
                sendMessageRef.current(lastUserMessage.content, { appendUserMessage: true });
            }
        }
    };
    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Use the Sitecore User ID from the context as the stable identifier for authentication
    const userId = user?.id;
    const siteId = pagesContext?.siteInfo?.id;

    if (!userId || !siteId) return;

    const recovered = loadChatRecovery(userId, siteId);
    if (!recovered) return;

    setConversationId(recovered.conversationId);
    setConversationTitle(recovered.conversationTitle);
    setAssistantType(recovered.assistantType as AssistantType);
    setMessages(
      recovered.messages.map((m) => ({
        role: m.role,
        content: m.content,
        images: m.images || [],
        timestamp: m.timestamp ? new Date(m.timestamp) : undefined,
      }))
    );

    const pending = recovered.pendingMessage;
    if (!pending) return;

    // If we're already authenticated, try to continue automatically.
    // Otherwise, keep the draft text so the user can send again after login.
    (async () => {
      const status = await checkAuthStatus(userId);
      setIsAuthenticated(status.authenticated);
      if (status.authenticated) {
        resumingFromAuthRef.current = true;
        await sendMessage(pending, { appendUserMessage: false });
      } else {
        setInput(pending);
      }
    })();
  }, [user?.id, pagesContext?.siteInfo?.id]);

  // Initial Auth Check
  useEffect(() => {
    if (user?.id) {
       checkAuthStatus(user.id).then(status => setIsAuthenticated(status.authenticated));
    }
  }, [user?.id]);
  
  const handleLogin = () => {
      if (!user?.id) return;
      const loginUrl = `/api/auth/login?userId=${encodeURIComponent(user.id)}&redirectUri=${encodeURIComponent(window.location.href)}`;
      window.location.href = loginUrl;
  };

  const sendMessage = async (
    messageText: string,
    options?: {
      appendUserMessage?: boolean;
    }
  ) => {
    const appendUserMessage = options?.appendUserMessage !== false;
    if (!messageText.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: messageText,
      timestamp: new Date(),
    };

    const snapshotMessages = appendUserMessage ? [...messages, userMessage] : [...messages];

    if (appendUserMessage) {
      setMessages(snapshotMessages);
      setInput('');
    }
    setIsLoading(true);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    try {
      const userId = user?.id;
      const siteId = pagesContext?.siteInfo?.id;
      const currentPageId = pagesContext?.pageInfo?.id;

      if (!userId || !siteId || !currentPageId) {
        console.error('Missing runtime context details:', { 
          hasUser: !!user, 
          userId, 
          hasPagesContext: !!pagesContext, 
          siteId, 
          currentPageId 
        });
        throw new Error(`Missing runtime context: UserID: ${userId ? 'present' : 'missing'}, SiteID: ${siteId ? 'present' : 'missing'}, PageID: ${currentPageId ? 'present' : 'missing'}`);
      }

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId,
          message: messageText,
          userId,
          siteId,
          currentPageId,
          environmentHost,
          selectedAsset,
          selectedComponentId,
          applicationId: applicationContext?.id,
          applicationContext,
          pagesContext,
          siteContext,
          hostUser: user,
        }),
        signal: abortControllerRef.current.signal,
      });

      // Handle authentication required response
      if (response.status === 401) {
        const errorData = await response.json();
        if (errorData.requiresAuth && errorData.authUrl) {
          // Persist the current conversation state so we can restore after OAuth.
          saveChatRecovery({
            userId,
            siteId,
            conversationId,
            conversationTitle,
            assistantType,
            messages: snapshotMessages.map((m) => ({
              role: m.role,
              content: m.content,
              images: m.images,
              timestamp: m.timestamp ? m.timestamp.toISOString() : undefined,
            })),
            pendingMessage: messageText,
          });

          toast.error('Authentication required. Redirecting to login...');
          setTimeout(() => {
            window.location.href = errorData.authUrl;
          }, 1500);
          setIsLoading(false);
          return;
        }
      }

      if (!response.ok) {
        // Attempt to surface a useful server-provided error message.
        let serverMessage: string | undefined;
        try {
          const data = await response.json();
          serverMessage = data?.message || data?.error;
        } catch {
          // ignore
        }
        throw new Error(serverMessage || `Failed to send message (${response.status})`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      // Buffer incomplete SSE lines across chunks.
      let sseBuffer = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          // Use streaming decode to avoid corrupting multi-byte characters across chunk boundaries.
          const chunk = decoder.decode(value, { stream: true });
          sseBuffer += chunk;

          // Process complete lines only; keep any partial line for the next chunk.
          while (true) {
            const newlineIndex = sseBuffer.indexOf('\n');
            if (newlineIndex === -1) break;

            const rawLine = sseBuffer.slice(0, newlineIndex);
            sseBuffer = sseBuffer.slice(newlineIndex + 1);

            const line = rawLine.trimEnd();
            if (!line) continue;

            if (line.startsWith('data: ')) {
              const payload = line.slice(6);
              try {
                const data = JSON.parse(payload);

                switch (data.type) {
                  case 'content':
                    assistantMessage += data.content;
                    const filteredContent = filterStreamContent(assistantMessage);
                    setMessages((prev) => {
                      const newMessages = [...prev];
                      const lastMessage = newMessages[newMessages.length - 1];
                      
                      if (lastMessage?.role === 'assistant') {
                        newMessages[newMessages.length - 1] = {
                          ...lastMessage,
                          content: filteredContent,
                        };
                      } else {
                        newMessages.push({
                          role: 'assistant',
                          content: filteredContent,
                          timestamp: new Date(),
                        });
                      }
                      
                      return newMessages;
                    });
                    break;

                  case 'client_action':
                    if (data.action === 'reload_page_canvas') {
                      onReloadCanvas?.();
                    } else if (data.action === 'navigate_to_page' && data.data?.itemId) {
                      onNavigateToPage?.(data.data.itemId);
                    } else if (data.action === 'execute_mutation' && data.data?.mutation) {
                       onExecuteMutation?.(data.data.mutation, data.data.payload);
                    } else if (data.action === 'auth_required' && data.data?.url) {
                       console.log('ChatPanel: Auth required, redirecting to', data.data.url);
                       
                       // Save state before redirecting
                        const userId = user?.id;
                        const siteId = pagesContext?.siteInfo?.id;
                        if (userId && siteId && conversationId) {
                            saveChatRecovery({
                                userId,
                                siteId,
                                conversationId,
                                conversationTitle,
                                assistantType,
                                messages: messages.map((m) => ({
                                    role: m.role,
                                    content: m.content,
                                    images: m.images,
                                    assets: m.assets,
                                    timestamp: m.timestamp ? m.timestamp.toISOString() : undefined,
                                })),
                                pendingMessage: input, // Save current input if any
                            });
                        }
                       
                       // Use a custom toast with a button to handle the popup properly and avoid iframe issues
                       toast((t) => (
                           <div className="flex flex-col gap-2">
                               <span>Authentication required to continue.</span>
                               <button 
                                   onClick={() => {
                                       window.open(data.data.url, '_blank');
                                       toast.dismiss(t.id);
                                   }}
                                   className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                               >
                                   Log in with Sitecore
                               </button>
                           </div>
                       ), { duration: Infinity, icon: '🔒' });
                    }
                    break;

                  case 'image':
                    setMessages((prev) => {
                      const newMessages = [...prev];
                      const lastMessage = newMessages[newMessages.length - 1];
                      const urls: string[] = data.urls || [];

                      if (lastMessage?.role === 'assistant') {
                        newMessages[newMessages.length - 1] = {
                          ...lastMessage,
                          images: [...(lastMessage.images || []), ...urls],
                          content: lastMessage.content || assistantMessage,
                          timestamp: new Date(),
                        };
                      } else {
                        newMessages.push({
                          role: 'assistant',
                          content: assistantMessage,
                          images: urls,
                          timestamp: new Date(),
                        });
                      }

                      return newMessages;
                    });
                    break;

                  case 'assets':
                    setMessages((prev) => {
                      const newMessages = [...prev];
                      const lastMessage = newMessages[newMessages.length - 1];
                      const assets = (data.assets || []) as Message['assets'];

                      if (!assets || assets.length === 0) return newMessages;

                      if (lastMessage?.role === 'assistant') {
                        newMessages[newMessages.length - 1] = {
                          ...lastMessage,
                          assets: [...(lastMessage.assets || []), ...assets],
                          timestamp: new Date(),
                        };
                      } else {
                        newMessages.push({
                          role: 'assistant',
                          content: assistantMessage,
                          assets: assets,
                          timestamp: new Date(),
                        });
                      }

                      return newMessages;
                    });
                    break;

                  case 'title':
                    setConversationTitle(data.title);
                    break;

                  case 'assistant_switch':
                    setAssistantType(data.newAssistant);
                    toast.success(
                      `Switched to ${data.newAssistant.replace('_', ' ').replace(/\b\w/g, (l: string) => l.toUpperCase())}`,
                      { icon: '🔄', duration: 3000 }
                    );
                    break;

                  case 'status':
                    if (data.message || data.toolName || data.toolDisplayName) {
                      const tool = data.toolDisplayName || data.toolName;
                      const baseMessage = data.message || 'Running a tool...';
                      const statusText = tool ? `${baseMessage} (Tool: ${tool})` : baseMessage;
                      toast(statusText, { icon: '🤖', duration: 2000 });
                    }
                    break;

                  case 'warning':
                    if (data.message) {
                      toast(data.message, { icon: '⚠️', duration: 5000 });
                    }
                    break;

                  case 'done':
                    setConversationId(data.conversationId);
                    setIsLoading(false);
                    if (resumingFromAuthRef.current) {
                      clearChatRecovery();
                      resumingFromAuthRef.current = false;
                    }
                    break;

                  case 'error':
                    console.error('Server error event:', data);
                    toast.error(data.message || 'An error occurred. Please try again.');
                    setIsLoading(false);
                    break;

                  default:
                    // Log unknown event types so we can extend the client safely.
                    console.warn('Unknown SSE event type:', data);
                    break;
                }
              } catch (e) {
                // If this happens, we likely received malformed JSON (or logs mixed into the stream).
                // Keep it visible for debugging.
                console.error('Failed to parse SSE data:', e, { line });
              }
            }
          }
        }
      }
    } catch (error: unknown) {
      if ((error as Error).name !== 'AbortError') {
        console.error('Error sending message:', error);
        toast.error('Failed to send message. Please try again.');
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  // Update ref to allow calling sendMessage from event listeners
  sendMessageRef.current = sendMessage;

  const handleSendMessage = async () => {
    await sendMessage(input, { appendUserMessage: true });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const loadConversation = async (convId: string) => {
    try {
      const response = await fetch(`/api/chat?conversationId=${convId}`);
      const data = await response.json();

      if (data.conversation) {
        setConversationId(data.conversation.id);
        setConversationTitle(data.conversation.title);
        setAssistantType(data.conversation.assistantType);
        setMessages(
          data.conversation.messages.map((m: { role: string; content: string; timestamp: string; images?: string[] }) => ({
            role: m.role,
            content: m.content,
            images: m.images || [],
            timestamp: new Date(m.timestamp),
          }))
        );
        setShowHistory(false);
      }
    } catch (error) {
      console.error('Error loading conversation:', error);
      toast.error('Failed to load conversation');
    }
  };

  const startNewConversation = () => {
    setConversationId(null);
    setConversationTitle(null);
    setMessages([]);
    setAssistantType('content_auditor');
    setShowHistory(false);
  };

  return (
    <>
      <Toaster position="top-center" />
      
      <div className="flex h-full">
        {/* Conversation History Sidebar */}
        {showHistory && (
          <div className="w-64 border-r border-gray-200 bg-gray-50">
            <ConversationHistory
              userId={user?.id || ''}
              siteId={pagesContext?.siteInfo?.id || ''}
              currentConversationId={conversationId}
              onSelectConversation={loadConversation}
              onNewConversation={startNewConversation}
              onClose={() => setShowHistory(false)}
            />
          </div>
        )}

        {/* Main Chat Panel */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="border-b border-gray-200 p-2 bg-white">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setShowHistory(!showHistory)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="Conversation History"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
                <div className="flex flex-col">
                   <h2 className="text-xs font-semibold text-gray-900">
                    {conversationTitle || 'AI Assistant'}
                   </h2>
                   {!isAuthenticated && (
                       <button 
                           onClick={handleLogin} 
                           className="text-[10px] text-blue-600 hover:text-blue-800 underline text-left"
                       >
                           Connect Sitecore
                       </button>
                   )}
                </div>
              </div>
              <div className="flex items-center gap-1">
                  {!isAuthenticated && (
                     <button
                        onClick={handleLogin}
                        className="p-1 px-2 bg-blue-50 text-blue-600 text-xs rounded hover:bg-blue-100 transition-colors mr-2 border border-blue-200"
                        title="Connect to Marketer MCP"
                     >
                       Connect
                     </button>
                  )}
                  <button
                    onClick={startNewConversation}
                    className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                    title="New Conversation"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </button>
              </div>
            </div>
            <AssistantBadge type={assistantType} />
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 mt-8">
                <p className="text-lg mb-2">👋 Welcome to your AI Assistant</p>
                <p className="text-sm">I can help you audit content, design campaigns, optimize SEO, and more.</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <MessageBubble key={idx} message={msg} />
            ))}
            {isLoading && (
              <div className="flex items-center space-x-2 text-gray-500">
                <div className="animate-pulse">●</div>
                <div className="animate-pulse delay-100">●</div>
                <div className="animate-pulse delay-200">●</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 p-4 bg-white">
            <div className="flex space-x-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask me anything..."
                className="flex-1 p-3 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={2}
                disabled={isLoading}
              />
              <button
                onClick={handleSendMessage}
                disabled={!input.trim() || isLoading}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
