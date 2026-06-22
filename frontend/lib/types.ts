export type RuntimeContext = {
  pageId: string;
  siteId: string;
  language: string;
  userName?: string;
  userEmail?: string;
};

export type MessageRole = "user" | "assistant";

export type ImageResult = {
  item_id: string;
  item_name: string;
  media_path: string;
  media_url: string | null;
  alt_text?: string | null;
  score: number;
};

export type Message = {
  id: string;
  role: MessageRole;
  content: string;
  createdAt?: string;
  imageResults?: ImageResult[];
  imageResultsQuery?: string;
};

export type ConversationSummary = {
  id: string;
  title: string | null;
  siteId: string;
  createdAt: string;
  updatedAt: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: Message[];
};

export type SseEvent =
  | { type: "conversationId"; id: string }
  | { type: "delta"; text: string }
  | { type: "tool_start"; tool: string }
  | { type: "tool_end"; tool: string }
  | { type: "canvas_reload" }
  | { type: "image_results"; results: ImageResult[]; query: string; count: number }
  | { type: "done" }
  | { type: "error"; code: string };

export type ApiError = {
  code: string;
  message?: string;
};
