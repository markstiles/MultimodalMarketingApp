"use client";

import { useChat } from "@/lib/hooks/useChat";
import { useSitecoreContext } from "@/lib/hooks/useSitecoreContext";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";

export function ChatPanel() {
  const { context, loading: contextLoading } = useSitecoreContext();
  const { messages, streaming, toolActivity, loading, error, send, retry } = useChat();

  function handleSend(text: string) {
    if (!context) return;
    send(text, context);
  }

  return (
    <div className="flex flex-col h-full bg-white" style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
<MessageList messages={messages} streaming={streaming} toolActivity={toolActivity} />

      {error && (
        <div
          className="mx-3 mb-2 flex items-center justify-between rounded px-3 py-1.5 text-xs"
          style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}
        >
          <span>Error: {error}</span>
          <button
            onClick={retry}
            className="ml-2 font-medium underline hover:no-underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <ChatInput
        onSend={handleSend}
        disabled={loading || contextLoading || !context}
      />
    </div>
  );
}
