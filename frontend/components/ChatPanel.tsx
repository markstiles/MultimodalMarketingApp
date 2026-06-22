"use client";

import { useEffect } from "react";
import { useChat } from "@/lib/hooks/useChat";
import { useSitecoreContext } from "@/lib/hooks/useSitecoreContext";
import type { ImageResult } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";

export function ChatPanel() {
  const { context, loading: contextLoading, reloadCanvas } = useSitecoreContext();
  const { messages, streaming, toolActivity, canvasReload, loading, error, send, retry } = useChat();

  // Reload the Sitecore Pages canvas whenever a write tool completes
  useEffect(() => {
    if (canvasReload > 0) reloadCanvas();
  }, [canvasReload, reloadCanvas]);

  function handleSend(text: string) {
    if (!context) return;
    send(text, context);
  }

  function handleUseImages(selected: ImageResult[]) {
    if (!context) return;
    const paths = selected.map((r) => r.media_path).join(", ");
    send(`Use these images: ${paths}`, context);
  }

  return (
    <div className="flex flex-col h-full bg-white" style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <MessageList messages={messages} streaming={streaming} toolActivity={toolActivity} loading={loading} onUseImages={handleUseImages} />

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
