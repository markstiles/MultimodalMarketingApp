"use client";

import { useState } from "react";
import type { ImageResult } from "@/lib/types";

const PAGE_SIZE = 12; // 3 rows × 4 columns

type Props = {
  results: ImageResult[];
  onUseSelected?: (selected: ImageResult[]) => void;
};

export function ImageResultsPanel({ results, onUseSelected }: Props) {
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const totalPages = Math.ceil(results.length / PAGE_SIZE);
  const start = page * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, results.length);
  const pageItems = results.slice(start, end);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleUseSelected() {
    const items = results.filter((r) => selected.has(r.item_id));
    onUseSelected?.(items);
  }

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
      {/* Header row */}
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span>
          Showing {start + 1}–{end} of {results.length} image{results.length !== 1 ? "s" : ""}
        </span>
        {selected.size > 0 && onUseSelected && (
          <button
            onClick={handleUseSelected}
            className="rounded px-2 py-0.5 text-xs font-medium text-white transition-colors"
            style={{ background: "var(--sc-purple)" }}
          >
            Use {selected.size} selected
          </button>
        )}
      </div>

      {/* Grid: 4 columns, up to 3 rows */}
      <div className="grid grid-cols-4 gap-2">
        {pageItems.map((item) => (
          <ImageTile
            key={item.item_id}
            item={item}
            selected={selected.has(item.item_id)}
            onToggle={() => toggleSelect(item.item_id)}
          />
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-2 flex items-center justify-center gap-3">
          <button
            onClick={() => setPage((p) => p - 1)}
            disabled={page === 0}
            className="flex h-6 w-6 items-center justify-center rounded text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            aria-label="Previous page"
          >
            ‹
          </button>
          <span className="text-xs text-slate-500">
            {page + 1} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={page >= totalPages - 1}
            className="flex h-6 w-6 items-center justify-center rounded text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700 disabled:opacity-30"
            aria-label="Next page"
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

type TileProps = {
  item: ImageResult;
  selected: boolean;
  onToggle: () => void;
};

function ImageTile({ item, selected, onToggle }: TileProps) {
  return (
    <div
      onClick={onToggle}
      className={`group relative cursor-pointer overflow-hidden rounded-md transition-all ${
        selected
          ? "ring-2 ring-offset-1"
          : "ring-1 ring-slate-200 hover:ring-slate-400"
      }`}
      style={selected ? { "--tw-ring-color": "var(--sc-purple)" } as React.CSSProperties : undefined}
      title={item.media_path}
    >
      {/* Square aspect ratio */}
      <div className="aspect-square w-full bg-slate-100">
        {item.media_url ? (
          <img
            src={item.media_url}
            alt={item.alt_text ?? item.item_name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-slate-300">
            <svg viewBox="0 0 24 24" className="h-8 w-8 fill-current">
              <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" />
            </svg>
          </div>
        )}
      </div>

      {/* Selection checkmark */}
      {selected && (
        <div
          className="absolute left-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-white"
          style={{ background: "var(--sc-purple)" }}
        >
          <svg viewBox="0 0 24 24" className="h-3 w-3 fill-current">
            <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z" />
          </svg>
        </div>
      )}

      {/* Open in new tab — top-right, visible on hover */}
      {item.media_url && (
        <a
          href={item.media_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded bg-black/50 text-white opacity-0 transition-opacity group-hover:opacity-100"
          title="Open in new tab"
        >
          <svg viewBox="0 0 24 24" className="h-3 w-3 fill-current">
            <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" />
          </svg>
        </a>
      )}

      {/* Media path label on hover */}
      <div className="absolute inset-x-0 bottom-0 truncate bg-black/40 px-1 py-0.5 text-center text-[10px] text-white opacity-0 transition-opacity group-hover:opacity-100">
        {item.media_path}
      </div>
    </div>
  );
}
