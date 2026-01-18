'use client';

import { useState, useRef, useEffect } from 'react';
import { EditorContext } from '@/lib/types/editor-messages';
import { AssistantType } from '@/lib/types/assistant';
import MessageBubble from '@/components/MessageBubble';
import AssistantBadge from '@/components/AssistantBadge';
import ConversationHistory from '@/components/ConversationHistory';
import toast, { Toaster } from 'react-hot-toast';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  timestamp?: Date;
}

interface ChatPanelProps {
  editorContext: EditorContext;
  onSendToEditor: (message: unknown) => void;
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

export default function ChatPanel({ editorContext, onSendToEditor }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversationTitle, setConversationTitle] = useState<string | null>(null);
  const [assistantType, setAssistantType] = useState<AssistantType>('content_auditor');
  const [showHistory, setShowHistory] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId,
          message: input,
          userId: editorContext.userId,
          siteId: editorContext.siteId,
          currentPageId: editorContext.pageId,
        }),
        signal: abortControllerRef.current.signal,
      });

      // Handle authentication required response
      if (response.status === 401) {
        const errorData = await response.json();
        if (errorData.requiresAuth && errorData.authUrl) {
          toast.error('Authentication required. Redirecting to login...');
          setTimeout(() => {
            window.location.href = errorData.authUrl;
          }, 1500);
          setIsLoading(false);
          return;
        }
      }

      if (!response.ok) throw new Error('Failed to send message');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantMessage = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

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

                  case 'done':
                    setConversationId(data.conversationId);
                    break;
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
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
              userId={editorContext.userId}
              siteId={editorContext.siteId}
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
          <div className="border-b border-gray-200 p-4 bg-white">
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
                <h2 className="text-lg font-semibold text-gray-900">
                  {conversationTitle || 'AI Assistant'}
                </h2>
              </div>
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
