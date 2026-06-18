"use client";

import { useEffect, useState } from "react";
import type { RuntimeContext } from "@/lib/types";

const RUNTIME_CONTEXT = process.env.NEXT_PUBLIC_RUNTIME_CONTEXT ?? "iframe";

function localContext(): RuntimeContext {
  return {
    pageId: process.env.NEXT_PUBLIC_LOCAL_PAGE_ID ?? "local-page",
    siteId: process.env.NEXT_PUBLIC_LOCAL_SITE_ID ?? "local-site",
    language: process.env.NEXT_PUBLIC_LOCAL_LANGUAGE ?? "en",
  };
}

function toRuntimeContext(ctx: {
  siteInfo?: { id?: string; language?: string };
  pageInfo?: { id?: string };
}): RuntimeContext {
  return {
    pageId: ctx.pageInfo?.id ?? "",
    siteId: ctx.siteInfo?.id ?? "",
    language: ctx.siteInfo?.language ?? "en",
  };
}

export function useSitecoreContext() {
  const [context, setContext] = useState<RuntimeContext | null>(
    RUNTIME_CONTEXT === "local" ? localContext() : null
  );
  const [loading, setLoading] = useState(RUNTIME_CONTEXT !== "local");

  useEffect(() => {
    if (RUNTIME_CONTEXT === "local") return;

    // iframe mode — lazy import keeps SDK out of the server bundle
    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    import("@sitecore-marketplace-sdk/client")
      .then(async ({ ClientSDK }) => {
        if (cancelled) return;

        // Handshake with the Sitecore Pages parent frame via postMessage.
        // origin is inferred from document.referrer; no explicit value needed.
        const client = await ClientSDK.init({
          target: window.parent,
          timeout: 10_000,
        });

        if (cancelled) return;

        const result = await client.query("pages.context", {
          subscribe: true,
          onSuccess: (ctx) => {
            if (!cancelled) {
              setContext(toRuntimeContext(ctx));
              setLoading(false);
            }
          },
        });

        // Seed with the initial value returned by the query
        if (result.data && !cancelled) {
          setContext(toRuntimeContext(result.data));
          setLoading(false);
        }

        unsubscribe = result.unsubscribe;
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  return { context, loading };
}
