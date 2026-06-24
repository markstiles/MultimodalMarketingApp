"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { ImageResult, Message, OptionItem } from "@/lib/types";
import { ImageResultsPanel } from "./ImageResultsPanel";
import { OptionsPanel } from "./OptionsPanel";

type Props = {
  message?: Message;
  streaming?: string;
  onImagesSelected?: (selected: ImageResult[]) => void;
  onSelectOption?: (item: OptionItem) => void;
};

export function MessageBubble({ message, streaming, onImagesSelected, onSelectOption }: Props) {
  const isUser = message?.role === "user";
  const hasImageResults = !!(message?.imageResults && message.imageResults.length > 0);
  const hasOptions = !!(message?.options && message.options.items.length > 0);
  const rawContent = streaming !== undefined ? streaming : message?.content ?? "";
  // When image results are present, suppress the LLM's text description of them
  const content = hasImageResults
    ? `Found ${message!.imageResults!.length} image${message!.imageResults!.length !== 1 ? "s" : ""}${message!.imageResultsQuery ? ` for "${message!.imageResultsQuery}"` : ""}.`
    : rawContent;

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
          {message?.imageResults && message.imageResults.length > 0 && (
            <ImageResultsPanel
              results={message.imageResults}
              onSelectionChange={onImagesSelected}
            />
          )}
          {hasOptions && onSelectOption && (
            <OptionsPanel
              options={message!.options!}
              onSelect={onSelectOption}
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
