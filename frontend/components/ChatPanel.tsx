"use client";

import { useEffect, useState } from "react";
import { useChat } from "@/lib/hooks/useChat";
import { useSitecoreContext } from "@/lib/hooks/useSitecoreContext";
import type { ImageResult, OptionItem } from "@/lib/types";
import { ChatInput } from "./ChatInput";
import { MessageList } from "./MessageList";

export function ChatPanel() {
  const { context, loading: contextLoading, reloadCanvas } = useSitecoreContext();
  const { messages, streaming, toolActivity, canvasReload, loading, error, send, retry } = useChat();
  const [pendingImages, setPendingImages] = useState<ImageResult[]>([]);

  // Reload the Sitecore Pages canvas whenever a write tool completes
  useEffect(() => {
    if (canvasReload > 0) reloadCanvas();
  }, [canvasReload, reloadCanvas]);

  function handleSend(text: string) {
    if (!context) return;
    let message = text;
    if (pendingImages.length > 0) {
      const paths = pendingImages.map((r) => r.media_path).join(", ");
      message = `[Selected images: ${paths}]\n\n${text}`;
      setPendingImages([]);
    }
    send(message, context);
  }

  function handleImagesSelected(items: ImageResult[]) {
    setPendingImages(items);
  }

  function handleSelectOption(item: OptionItem) {
    if (!context) return;
    const msg = item.id && item.id !== item.label
      ? `${item.label} (id: ${item.id})`
      : item.label;
    send(msg, context);
  }

  return (
    <div className="flex flex-col h-full bg-white" style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
      <MessageList
        messages={messages}
        streaming={streaming}
        toolActivity={toolActivity}
        loading={loading}
        onImagesSelected={handleImagesSelected}
        onSelectOption={handleSelectOption}
      />

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
        pendingImages={pendingImages}
        onClearImages={() => setPendingImages([])}
      />
    </div>
  );
}
