"use client";

import { useState } from "react";

import type { OptionItem, OptionsPayload } from "@/lib/types";

type Props = {
  options: OptionsPayload;
  onSelect: (item: OptionItem) => void;
};

export function OptionsPanel({ options, onSelect }: Props) {
  const { items, prompt, option_type } = options;
  const [selectedId, setSelectedId] = useState<string | null>(null);

  function handleClick(item: OptionItem) {
    if (selectedId !== null) return;
    setSelectedId(item.id);
    onSelect(item);
  }

  return (
    <div className="mt-2 p-1">
      {prompt && (
        <p className="mb-2 text-xs font-medium" style={{ color: "#374151" }}>{prompt}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {items.map((item) => {
          const isSelected = selectedId === item.id;
          const isDisabled = selectedId !== null;
          return (
            <button
              key={item.id}
              onClick={() => handleClick(item)}
              disabled={isDisabled}
              className="rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2"
              style={{
                background: isSelected
                  ? "var(--sc-purple-hover)"
                  : isDisabled
                  ? "#e5e7eb"
                  : "var(--sc-purple-light)",
                color: isSelected ? "#ffffff" : isDisabled ? "#9ca3af" : "var(--sc-purple)",
                cursor: isDisabled ? "default" : "pointer",
              }}
              onMouseEnter={(e) => {
                if (isDisabled) return;
                e.currentTarget.style.background = "var(--sc-purple-hover)";
                e.currentTarget.style.color = "#ffffff";
              }}
              onMouseLeave={(e) => {
                if (isDisabled) return;
                e.currentTarget.style.background = "var(--sc-purple-light)";
                e.currentTarget.style.color = "var(--sc-purple)";
              }}
            >
              {item.thumbnail && option_type === "image" && (
                <img
                  src={item.thumbnail}
                  alt={item.label}
                  className="mb-1 h-16 w-full rounded object-cover"
                  loading="lazy"
                />
              )}
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
