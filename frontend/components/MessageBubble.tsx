"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Message } from "@/lib/types";

type Props = {
  message?: Message;
  streaming?: string;
};

export function MessageBubble({ message, streaming }: Props) {
  const isUser = message?.role === "user";
  const content = streaming !== undefined ? streaming : message?.content ?? "";

  if (streaming !== undefined || !isUser) {
    // Assistant message — left-aligned, clean gray
    return (
      <div className="flex justify-start mb-2.5">
        <div
          className="max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed break-words"
          style={{ background: "#f3f4f6", color: "#1f2937" }}
        >
          <div className="prose prose-neutral max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_*]:text-xs [&_table]:block [&_table]:overflow-x-auto">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </div>
          {streaming !== undefined && (
            <span
              className="inline-block w-0.5 h-3 ml-0.5 align-middle"
              style={{ background: "var(--sc-purple)", animation: "pulse 1s infinite" }}
            />
          )}
        </div>
      </div>
    );
  }

  // User message — right-aligned, Sitecore violet
  return (
    <div className="flex justify-end mb-2.5">
      <div
        className="max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed whitespace-pre-wrap break-words text-white"
        style={{ background: "var(--sc-purple)" }}
      >
        {content}
      </div>
    </div>
  );
}
