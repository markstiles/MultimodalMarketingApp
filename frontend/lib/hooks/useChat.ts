"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ImageResult, Message, OptionsPayload, RuntimeContext, SseEvent } from "@/lib/types";

function pickupUrlConversationId(): string | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const id = params.get("conversationId");
  if (id) {
    params.delete("conversationId");
    const newSearch = params.toString();
    const newUrl =
      window.location.pathname + (newSearch ? `?${newSearch}` : "") + window.location.hash;
    window.history.replaceState(null, "", newUrl);
  }
  return id;
}

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm your Sitecore marketing assistant. I can help you write and edit page content, audit components, plan campaigns, and work with your media library — all without leaving the editor.\n\nWhat would you like to work on?",
};

export function useChat(initialConversationId?: string | null) {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [streaming, setStreaming] = useState<string>("");
  const [toolActivity, setToolActivity] = useState<string | null>(null);
  const [canvasReload, setCanvasReload] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId ?? null
  );
  const pendingImageResultsRef = useRef<ImageResult[] | null>(null);
  const pendingImageQueryRef = useRef<string>("");
  const pendingOptionsRef = useRef<OptionsPayload | null>(null);
  const jobPollsRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // On mount, pick up conversationId from URL (set by auth callback after login redirect)
  useEffect(() => {
    const urlId = pickupUrlConversationId();
    if (urlId) setConversationId(urlId);
  }, []);

  // Clean up all job poll intervals on unmount
  useEffect(() => {
    const polls = jobPollsRef.current;
    return () => { polls.forEach((id) => clearInterval(id)); };
  }, []);

  const abortRef = useRef<AbortController | null>(null);

  const startJobPoll = useCallback((handle: string, siteName: string) => {
    if (jobPollsRef.current.has(handle)) return;
    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs?handle=${encodeURIComponent(handle)}`);
        if (!res.ok) return;
        const data = await res.json();
        const status: string = data.status ?? "";
        if (status === "Completed" || status === "Failed") {
          clearInterval(intervalId);
          jobPollsRef.current.delete(handle);
          const content = status === "Completed"
            ? `Site '${siteName}' has been created successfully and is ready to use.`
            : `Site creation for '${siteName}' failed. Please try again or check the Sitecore dashboard.`;
          setMessages((prev) => [
            ...prev,
            { id: crypto.randomUUID(), role: "assistant", content },
          ]);
        }
      } catch {
        // network hiccup — keep polling
      }
    }, 5000);
    jobPollsRef.current.set(handle, intervalId);
  }, []);

  const send = useCallback(
    async (text: string, context: RuntimeContext) => {
      if (!text.trim() || loading) return;

      setLoading(true);
      setError(null);
      setStreaming("");
      setToolActivity(null);
      pendingImageResultsRef.current = null;
      pendingImageQueryRef.current = "";
      pendingOptionsRef.current = null;
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", content: text },
      ]);

      abortRef.current = new AbortController();

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            conversationId: conversationId,
            context,
          }),
          signal: abortRef.current.signal,
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let assistantText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const raw = line.slice(6).trim();
            if (!raw) continue;

            let event: SseEvent;
            try {
              event = JSON.parse(raw);
            } catch {
              continue;
            }

            if (event.type === "conversationId") {
              setConversationId(event.id);
            } else if (event.type === "delta") {
              assistantText += event.text;
              setStreaming(assistantText);
              setToolActivity(null);
            } else if (event.type === "tool_start") {
              setToolActivity(event.tool);
            } else if (event.type === "tool_end") {
              setToolActivity(null);
            } else if (event.type === "image_results") {
              console.log("[useChat] image_results received:", event.results.length, "items");
              pendingImageResultsRef.current = event.results;
              pendingImageQueryRef.current = event.query ?? "";
            } else if (event.type === "options") {
              console.log("[useChat] options received:", event.count, "items type=", event.option_type);
              pendingOptionsRef.current = {
                items: event.items,
                prompt: event.prompt,
                option_type: event.option_type,
                count: event.count,
              };
            } else if (event.type === "job_started") {
              startJobPoll(event.handle, event.name);
            } else if (event.type === "canvas_reload") {
              setCanvasReload((n) => n + 1);
            } else if (event.type === "done") {
              const imageResults = pendingImageResultsRef.current ?? undefined;
              const imageResultsQuery = pendingImageQueryRef.current || undefined;
              const options = pendingOptionsRef.current ?? undefined;
              pendingImageResultsRef.current = null;
              pendingImageQueryRef.current = "";
              pendingOptionsRef.current = null;
              setMessages((prev) => [
                ...prev,
                {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content: assistantText,
                  imageResults,
                  imageResultsQuery,
                  options,
                },
              ]);
              setStreaming("");
              setToolActivity(null);
            } else if (event.type === "error") {
              setError(event.code);
              setStreaming("");
              setToolActivity(null);
            }
          }
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name !== "AbortError") {
          setError("network_error");
        }
      } finally {
        setLoading(false);
        setStreaming("");
        setToolActivity(null);
      }
    },
    [loading, conversationId, startJobPoll]
  );

  const retry = useCallback(() => {
    setError(null);
  }, []);

  return { messages, streaming, toolActivity, canvasReload, loading, error, conversationId, send, retry };
}
