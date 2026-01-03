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
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`w-full p-3 text-left hover:bg-gray-100 transition-colors ${
                  currentConversationId === conv.id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
                }`}
              >
                <div className="font-medium text-sm text-gray-900 truncate">
                  {conv.title || 'Untitled Conversation'}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {formatDate(conv.updatedAt)}
                </div>
                <div className="text-xs text-gray-400 mt-1 capitalize">
                  {conv.assistantType.replace('_', ' ')}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
