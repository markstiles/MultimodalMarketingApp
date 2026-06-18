"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RuntimeContext } from "@/lib/types";

const RUNTIME_CONTEXT = process.env.NEXT_PUBLIC_RUNTIME_CONTEXT ?? "iframe";

function localContext(): RuntimeContext {
  return {
    pageId: process.env.NEXT_PUBLIC_LOCAL_PAGE_ID ?? "local-page",
    siteId: process.env.NEXT_PUBLIC_LOCAL_SITE_ID ?? "local-site",
    language: process.env.NEXT_PUBLIC_LOCAL_LANGUAGE ?? "en",
  };
}

function toRuntimeContext(
  ctx: { siteInfo?: { id?: string; language?: string }; pageInfo?: { id?: string } },
  user?: { name?: string; email?: string } | null
): RuntimeContext {
  return {
    pageId: ctx.pageInfo?.id ?? "",
    siteId: ctx.siteInfo?.id ?? "",
    language: ctx.siteInfo?.language ?? "en",
    userName: user?.name ?? undefined,
    userEmail: user?.email ?? undefined,
  };
}

export function useSitecoreContext() {
  const [context, setContext] = useState<RuntimeContext | null>(
    RUNTIME_CONTEXT === "local" ? localContext() : null
  );
  const [loading, setLoading] = useState(RUNTIME_CONTEXT !== "local");
  const clientRef = useRef<any>(null);

  useEffect(() => {
    if (RUNTIME_CONTEXT === "local") return;

    let cancelled = false;
    let unsubscribe: (() => void) | undefined;

    import("@sitecore-marketplace-sdk/client")
      .then(async ({ ClientSDK }) => {
        if (cancelled) return;

        const client = await ClientSDK.init({ target: window.parent, timeout: 10_000 });
        if (cancelled) return;
        clientRef.current = client;

        // Fetch user info once (no subscription support)
        let user: { name?: string; email?: string } | null = null;
        try {
          const userResult = await client.query("host.user");
          if (userResult.data) user = userResult.data;
        } catch {
          // non-fatal — user info is optional context
        }

        const result = await client.query("pages.context", {
          subscribe: true,
          onSuccess: (ctx) => {
            if (!cancelled) {
              setContext(toRuntimeContext(ctx, user));
              setLoading(false);
            }
          },
        });

        if (result.data && !cancelled) {
          setContext(toRuntimeContext(result.data, user));
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

  const reloadCanvas = useCallback(() => {
    clientRef.current?.mutate("pages.reloadCanvas");
  }, []);

  return { context, loading, reloadCanvas };
}
