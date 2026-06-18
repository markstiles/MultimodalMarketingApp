"use client";

import { useEffect, useState } from "react";

const RUNTIME_CONTEXT = process.env.NEXT_PUBLIC_RUNTIME_CONTEXT ?? "iframe";

type Props = {
  children: React.ReactNode;
};

export function AuthGate({ children }: Props) {
  const [status, setStatus] = useState<"loading" | "authenticated" | "unauthenticated">(
    // In local or iframe mode auth is handled externally — skip the loading state
    RUNTIME_CONTEXT !== "standalone" ? "authenticated" : "loading"
  );

  useEffect(() => {
    // local: already authenticated via stub identity
    // iframe: user is authenticated by Sitecore's parent frame — no redirect possible inside an iframe
    // standalone: perform the Auth0 session check
    if (RUNTIME_CONTEXT !== "standalone") return;

    fetch("/api/auth/status")
      .then((r) => r.json())
      .then((data) => {
        setStatus(data.authenticated ? "authenticated" : "unauthenticated");
      })
      .catch(() => setStatus("unauthenticated"));
  }, []);

  if (status === "loading") {
    return (
      <div className="flex h-full items-center justify-center text-slate-400 text-sm">
        Loading…
      </div>
    );
  }

  if (status === "unauthenticated") {
    const loginUrl = `/api/auth/login?returnTo=${encodeURIComponent(window.location.pathname)}`;
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6 text-center">
        <p className="text-sm text-slate-600">
          Sign in to use the Sitecore marketing assistant.
        </p>
        <a
          href={loginUrl}
          className="text-xs font-medium text-white transition-colors"
          style={{ background: "var(--sc-purple)", borderRadius: "6px", padding: "6px 16px" }}
        >
          Sign in with Sitecore
        </a>
      </div>
    );
  }

  return <>{children}</>;
}
