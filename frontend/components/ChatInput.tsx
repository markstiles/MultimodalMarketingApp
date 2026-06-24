"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";
import type { ImageResult } from "@/lib/types";

const MAX_CHARS = 32000;

type Props = {
  onSend: (text: string) => void;
  disabled: boolean;
  pendingImages?: ImageResult[];
  onClearImages?: () => void;
};

export function ChatInput({ onSend, disabled, pendingImages, onClearImages }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!disabled) textareaRef.current?.focus();
  }, [disabled]);

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.focus();
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function handleInput() {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 120) + "px";
    }
  }

  const near = value.length > MAX_CHARS * 0.9;
  const imageCount = pendingImages?.length ?? 0;

  return (
    <div
      className="px-3 py-2 shrink-0"
      style={{ borderTop: "1px solid var(--sc-border)", background: "#fafafa" }}
    >
      {imageCount > 0 && (
        <div className="mb-1.5 flex items-center gap-1.5 text-xs" style={{ color: "var(--sc-purple)" }}>
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 shrink-0 fill-current">
            <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" />
          </svg>
          <span>
            {imageCount} image{imageCount !== 1 ? "s" : ""} attached
          </span>
          <button
            onClick={onClearImages}
            className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full text-slate-400 hover:bg-slate-200 hover:text-slate-600"
            title="Clear attached images"
          >
            ×
          </button>
        </div>
      )}
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          id="chat-message"
          name="chat-message"
          value={value}
          onChange={(e) => setValue(e.target.value.slice(0, MAX_CHARS))}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={disabled}
          placeholder={disabled ? "Loading…" : "Ask anything about your content…"}
          rows={1}
          className="flex-1 resize-none text-xs leading-relaxed"
          style={{
            border: "1px solid var(--sc-border)",
            borderRadius: "6px",
            padding: "6px 10px",
            outline: "none",
            background: disabled ? "#f9fafb" : "#ffffff",
            color: "#1f2937",
            maxHeight: "120px",
            overflowY: "auto",
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = "var(--sc-purple)")}
          onBlur={(e) => (e.currentTarget.style.borderColor = "var(--sc-border)")}
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="shrink-0 text-xs font-medium text-white transition-colors"
          style={{
            background: disabled || !value.trim() ? "#d1d5db" : "var(--sc-purple)",
            borderRadius: "6px",
            padding: "6px 12px",
            cursor: disabled || !value.trim() ? "default" : "pointer",
          }}
          onMouseEnter={(e) => {
            if (!disabled && value.trim())
              e.currentTarget.style.background = "var(--sc-purple-hover)";
          }}
          onMouseLeave={(e) => {
            if (!disabled && value.trim())
              e.currentTarget.style.background = "var(--sc-purple)";
          }}
        >
          Send
        </button>
      </div>
      {near && (
        <p className="mt-1 text-right text-xs" style={{ color: "var(--sc-muted)" }}>
          {value.length}/{MAX_CHARS}
        </p>
      )}
    </div>
  );
}
