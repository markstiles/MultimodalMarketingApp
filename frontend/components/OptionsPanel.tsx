"use client";

import type { OptionItem, OptionsPayload } from "@/lib/types";

type Props = {
  options: OptionsPayload;
  onSelect: (item: OptionItem) => void;
};

export function OptionsPanel({ options, onSelect }: Props) {
  const { items, prompt, option_type } = options;

  return (
    <div className="mt-2 p-1">
      {prompt && (
        <p className="mb-2 text-xs font-medium" style={{ color: "#374151" }}>{prompt}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item)}
            className="rounded-md px-3 py-1.5 text-xs font-medium text-white transition-colors focus-visible:outline-none focus-visible:ring-2"
            style={{ background: "var(--sc-purple-light)", color: "var(--sc-purple)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = "var(--sc-purple-hover)";
              e.currentTarget.style.color = "#ffffff";
            }}
            onMouseLeave={(e) => {
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
        ))}
      </div>
    </div>
  );
}
