"use client";

import type { OptionItem, OptionsPayload } from "@/lib/types";

type Props = {
  options: OptionsPayload;
  onSelect: (item: OptionItem) => void;
};

export function OptionsPanel({ options, onSelect }: Props) {
  const { items, prompt, option_type } = options;

  return (
    <div className="mt-2 rounded-lg border border-border bg-background/50 p-3">
      {prompt && (
        <p className="mb-3 text-sm font-medium text-foreground">{prompt}</p>
      )}
      <div className="flex flex-wrap gap-2">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => onSelect(item)}
            className="group flex flex-col items-start gap-0.5 rounded-md border border-border bg-card px-3 py-2 text-left text-sm shadow-sm transition-colors hover:border-primary hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            title={item.description}
          >
            {item.thumbnail && option_type === "image" && (
              <img
                src={item.thumbnail}
                alt={item.label}
                className="mb-1 h-16 w-full rounded object-cover"
                loading="lazy"
              />
            )}
            <span className="font-medium text-foreground group-hover:text-primary">
              {item.label}
            </span>
            {item.description && (
              <span className="text-xs text-muted-foreground">{item.description}</span>
            )}
            {item.metadata && (
              <span className="text-xs text-muted-foreground/70">{item.metadata}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
