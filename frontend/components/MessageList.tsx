"use client";

import { useEffect, useRef } from "react";
import type { ImageResult, Message, OptionItem } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";

type Props = {
  messages: Message[];
  streaming: string;
  toolActivity?: string | null;
  loading?: boolean;
  onUseImages?: (selected: ImageResult[]) => void;
  onSelectOption?: (item: OptionItem) => void;
};

function formatToolName(tool: string): string {
  return tool.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

export function MessageList({ messages, streaming, toolActivity, loading, onUseImages, onSelectOption }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming]);

  if (messages.length === 0 && !streaming && !loading) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-400 text-sm">
        Ask me anything about your Sitecore content.
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 chat-scroll">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} onUseImages={onUseImages} onSelectOption={onSelectOption} />
      ))}
      {streaming && <MessageBubble streaming={streaming} />}
      {toolActivity && !streaming && (
        <div className="flex justify-start mb-2.5">
          <div
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
            style={{ background: "#f3f4f6", color: "#6b7280" }}
          >
            <span
              className="inline-block w-3 h-3 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: "var(--sc-purple)", borderTopColor: "transparent" }}
            />
            {formatToolName(toolActivity)}…
          </div>
        </div>
      )}
      {loading && !streaming && !toolActivity && (
        <div className="flex justify-start mb-2.5">
          <div className="flex items-center gap-1 rounded-lg px-3 py-3" style={{ background: "#f3f4f6" }}>
            {[0, 160, 320].map((delay) => (
              <span
                key={delay}
                className="block w-1.5 h-1.5 rounded-full animate-bounce"
                style={{ background: "var(--sc-purple)", animationDelay: `${delay}ms` }}
              />
            ))}
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
