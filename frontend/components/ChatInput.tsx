"use client";

import { KeyboardEvent, useEffect, useRef, useState } from "react";

const MAX_CHARS = 32000;

type Props = {
  onSend: (text: string) => void;
  disabled: boolean;
};

export function ChatInput({ onSend, disabled }: Props) {
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

  return (
    <div
      className="px-3 py-2 shrink-0"
      style={{ borderTop: "1px solid var(--sc-border)", background: "#fafafa" }}
    >
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
