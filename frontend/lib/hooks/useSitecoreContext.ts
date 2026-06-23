"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RuntimeContext } from "@/lib/types";

/**
 * Normalize a Sitecore GUID that may arrive with curly braces, e.g. {B0A6...} → b0a6...
 * Returns empty string unchanged so callers can detect "unavailable" via falsy check.
 */
function normalizeGuid(value: string | undefined | null): string {
  if (!value) return "";
  return value.replace(/^\{|\}$/g, "").toLowerCase();
}

/**
 * Fallback context used when running standalone (not in Pages editor) or when the
 * SDK fails to provide context. Empty string for IDs means "unavailable" — the backend
 * system prompt will instruct the LLM to call list_sites / ask the user as needed.
 * Set NEXT_PUBLIC_LOCAL_SITE_ID / NEXT_PUBLIC_LOCAL_PAGE_ID in .env.local to seed
 * known IDs for local development without needing the Pages editor.
 */
function localContext(): RuntimeContext {
  return {
    pageId: normalizeGuid(process.env.NEXT_PUBLIC_LOCAL_PAGE_ID),
    siteId: normalizeGuid(process.env.NEXT_PUBLIC_LOCAL_SITE_ID),
    language: process.env.NEXT_PUBLIC_LOCAL_LANGUAGE ?? "en",
  };
}

function toRuntimeContext(
  ctx: { siteInfo?: { id?: string; language?: string }; pageInfo?: { id?: string } },
  user?: { name?: string; email?: string } | null
): RuntimeContext {
  return {
    // Normalize GUIDs — the SDK may return {GUID} format with braces
    pageId: normalizeGuid(ctx.pageInfo?.id),
    siteId: normalizeGuid(ctx.siteInfo?.id),
    language: ctx.siteInfo?.language ?? "en",
    userName: user?.name ?? undefined,
    userEmail: user?.email ?? undefined,
  };
}

export function useSitecoreContext() {
  const [context, setContext] = useState<RuntimeContext | null>(null);
  const [loading, setLoading] = useState(true);
  const clientRef = useRef<any>(null);

  useEffect(() => {
    const inIframe = window.self !== window.parent;
    console.log("[useSitecoreContext] inIframe =", inIframe);

    if (!inIframe) {
      console.log("[useSitecoreContext] standalone — using local context:", localContext());
      setContext(localContext());
      setLoading(false);
      return;
    }

    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    import("@sitecore-marketplace-sdk/client")
      .then(async ({ ClientSDK }) => {
        if (cancelled) return;
        console.log("[useSitecoreContext] SDK loaded, initialising...");

        const client = await ClientSDK.init({ target: window.parent, timeout: 10_000 });
        if (cancelled) return;
        console.log("[useSitecoreContext] SDK initialised");
        clientRef.current = client;

        let user: { name?: string; email?: string } | null = null;
        try {
          const userResult = await client.query("host.user");
          if (userResult.data) user = userResult.data;
          console.log("[useSitecoreContext] user =", user);
        } catch {
          // non-fatal — user info is optional context
        }

        try {
          const result = await client.query("pages.context", {
            subscribe: true,
            onSuccess: (ctx) => {
              if (!cancelled) {
                console.log("[useSitecoreContext] pages.context update:", ctx);
                setContext(toRuntimeContext(ctx, user));
                setLoading(false);
              }
            },
          });

          console.log("[useSitecoreContext] pages.context initial result:", result?.data);
          if (!cancelled) {
            setContext(result?.data ? toRuntimeContext(result.data, user) : localContext());
            setLoading(false);
          }

          unsubscribe = result?.unsubscribe;
        } catch (err) {
          console.warn("[useSitecoreContext] pages.context not available, using local context:", err);
          if (!cancelled) {
            setContext(localContext());
            setLoading(false);
          }
        }
      })
      .catch((err) => {
        console.warn("[useSitecoreContext] SDK failed, falling back to local context:", err);
        if (!cancelled) {
          setContext(localContext());
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
      unsubscribe?.();
    };
  }, []);

  const reloadCanvas = useCallback(() => {
    clientRef.current?.mutate("pages.reloadCanvas");
  }, []);

  /** Tell the Pages editor to navigate its content tree to the given page ID. */
  const navigateToPage = useCallback((pageId: string) => {
    clientRef.current?.mutate("pages.navigate", { pageId });
  }, []);

  return { context, loading, reloadCanvas, navigateToPage };
}
