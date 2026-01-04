'use client';

import { useState, useEffect } from 'react';

interface Conversation {
  id: string;
  title: string | null;
  assistantType: string;
  createdAt: string;
  updatedAt: string;
}

interface ConversationHistoryProps {
  userId: string;
  siteId: string;
  currentConversationId: string | null;
  onSelectConversation: (conversationId: string) => void;
  onNewConversation: () => void;
  onClose: () => void;
}

export default function ConversationHistory({
  userId,
  siteId,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onClose,
}: ConversationHistoryProps) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);

  useEffect(() => {
    loadConversations();
  }, [userId, siteId]);

  const loadConversations = async () => {
    try {
      const response = await fetch(`/api/chat?userId=${userId}&siteId=${siteId}`);
      const data = await response.json();
      setConversations(data.conversations || []);
    } catch (error) {
      console.error('Error loading conversations:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (conversationId: string) => {
    if (isDeleting) return;
    setIsDeleting(conversationId);

    try {
      await fetch(`/api/chat?conversationId=${conversationId}&userId=${userId}&siteId=${siteId}`, {
        method: 'DELETE',
      });

      setConversations((prev) => prev.filter((c) => c.id !== conversationId));

      if (currentConversationId === conversationId) {
        onNewConversation();
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    } finally {
      setIsDeleting(null);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-900">Conversations</h3>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <button
          onClick={onNewConversation}
          className="w-full px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          + New Conversation
        </button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-sm">Loading...</p>
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-500">
            <p className="text-sm">No conversations yet</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {conversations.map((conv) => (
              <div
                key={conv.id}
                className={`w-full text-left hover:bg-gray-100 transition-colors flex items-stretch justify-between ${
                  currentConversationId === conv.id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
                }`}
              >
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className="relative w-4/5 text-left p-3 overflow-hidden"
                >
                  <div
                    className="font-medium text-sm text-gray-900 truncate"
                    title={conv.title || 'Untitled Conversation'}
                  >
                    {conv.title || 'Untitled Conversation'}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {formatDate(conv.updatedAt)}
                  </div>
                  <div className="text-xs text-gray-400 mt-1 capitalize truncate">
                    {conv.assistantType.replace('_', ' ')}
                  </div>
                  <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-white via-white/70 to-transparent" />
                </button>
                <button
                  onClick={() => handleDelete(conv.id)}
                  className="w-12 flex items-center justify-center border-l border-gray-200 text-gray-500 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Delete conversation"
                  disabled={isDeleting === conv.id}
                >
                  {isDeleting === conv.id ? (
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V5a1 1 0 00-1-1h-4a1 1 0 00-1 1v2M4 7h16" />
                    </svg>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
