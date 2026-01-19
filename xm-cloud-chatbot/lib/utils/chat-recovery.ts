export interface RecoverableMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  images?: string[];
  timestamp?: string;
}

export interface ChatRecoveryState {
  version: 1;
  storedAt: number;
  userId: string;
  siteId: string;
  conversationId: string | null;
  conversationTitle: string | null;
  assistantType: string;
  messages: RecoverableMessage[];
  pendingMessage?: string;
}

const STORAGE_KEY = 'xmcloud-chatbot.chat-recovery.v1';
const MAX_AGE_MS = 15 * 60 * 1000; // 15 minutes

export function saveChatRecovery(state: Omit<ChatRecoveryState, 'version' | 'storedAt'>): void {
  if (typeof window === 'undefined') return;

  const payload: ChatRecoveryState = {
    version: 1,
    storedAt: Date.now(),
    ...state,
  };

  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore storage failures (private mode, quota, etc.)
  }
}

export function loadChatRecovery(userId: string, siteId: string): ChatRecoveryState | null {
  if (typeof window === 'undefined') return null;

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<ChatRecoveryState>;
    if (parsed.version !== 1) return null;
    if (!parsed.storedAt || Date.now() - parsed.storedAt > MAX_AGE_MS) return null;
    if (parsed.userId !== userId || parsed.siteId !== siteId) return null;

    if (!Array.isArray(parsed.messages)) return null;

    return parsed as ChatRecoveryState;
  } catch {
    return null;
  }
}

export function clearChatRecovery(): void {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
