import type { ChatSession, Message, SearchMode, Source } from "./types";

const STORAGE_KEY = "insurance-rag-chat-history-v1";
const TITLE_MAX_LENGTH = 28;
const modes = new Set<SearchMode>(["quick", "semantic", "web"]);

export function createId(): string {
  return crypto.randomUUID();
}

export function createEmptySession(now = new Date().toISOString()): ChatSession {
  return {
    id: createId(),
    title: "新对话",
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function sessionHasUserMessage(session: ChatSession): boolean {
  return session.messages.some((message) => message.role === "user" && message.content.trim());
}

export function titleFromMessages(messages: Message[]): string {
  const firstUserMessage = messages.find((message) => message.role === "user" && message.content.trim());
  if (!firstUserMessage) return "新对话";
  const text = firstUserMessage.content.trim().replace(/\s+/g, " ");
  return text.length > TITLE_MAX_LENGTH ? `${text.slice(0, TITLE_MAX_LENGTH)}...` : text;
}

export function refreshSession(session: ChatSession, messages: Message[], updatedAt = new Date().toISOString()): ChatSession {
  return {
    ...session,
    title: titleFromMessages(messages),
    messages,
    updatedAt,
  };
}

function isSearchMode(value: unknown): value is SearchMode {
  return typeof value === "string" && modes.has(value as SearchMode);
}

function normalizeMessage(value: unknown): Message | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<Message>;
  if (typeof item.id !== "string" || typeof item.content !== "string") return null;
  if (item.role !== "user" && item.role !== "ai") return null;

  return {
    id: item.id,
    role: item.role,
    content: item.content,
    mode: isSearchMode(item.mode) ? item.mode : undefined,
    isStreaming: false,
    isLoading: false,
    sources: Array.isArray(item.sources) ? item.sources.map(normalizeSource).filter((source): source is Source => Boolean(source)) : undefined,
    error: typeof item.error === "string" ? item.error : undefined,
  };
}

// 旧版本历史中的 sources 是字符串标签（如"本地资料库"），没有引用价值，导入时丢弃
function normalizeSource(value: unknown): Source | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<Source>;
  if (typeof item.id !== "number" || typeof item.title !== "string" || typeof item.snippet !== "string") return null;
  return {
    id: item.id,
    kind: item.kind === "web" ? "web" : "local",
    title: item.title,
    section: typeof item.section === "string" ? item.section : undefined,
    snippet: item.snippet,
    url: typeof item.url === "string" && /^https?:\/\//.test(item.url) ? item.url : undefined,
    score: typeof item.score === "number" ? item.score : undefined,
  };
}

function normalizeSession(value: unknown): ChatSession | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<ChatSession>;
  if (typeof item.id !== "string") return null;
  if (!Array.isArray(item.messages)) return null;

  const messages = item.messages.map(normalizeMessage).filter((message): message is Message => Boolean(message));
  const createdAt = typeof item.createdAt === "string" ? item.createdAt : new Date().toISOString();
  const updatedAt = typeof item.updatedAt === "string" ? item.updatedAt : createdAt;

  return {
    id: item.id,
    title: titleFromMessages(messages),
    messages,
    createdAt,
    updatedAt,
  };
}

export function visibleSessions(sessions: ChatSession[]): ChatSession[] {
  return sessions
    .filter(sessionHasUserMessage)
    .slice()
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
}

export function loadSessionState(): { sessions: ChatSession[]; currentSessionId: string } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      const emptySession = createEmptySession();
      return { sessions: [emptySession], currentSessionId: emptySession.id };
    }

    const parsed = JSON.parse(raw) as { sessions?: unknown; currentSessionId?: unknown };
    const restored = Array.isArray(parsed.sessions)
      ? parsed.sessions.map(normalizeSession).filter((session): session is ChatSession => Boolean(session))
      : [];
    const sessions = restored.length > 0 ? restored : [createEmptySession()];
    const currentSessionId =
      typeof parsed.currentSessionId === "string" && sessions.some((session) => session.id === parsed.currentSessionId)
        ? parsed.currentSessionId
        : sessions[0].id;

    return { sessions, currentSessionId };
  } catch {
    const emptySession = createEmptySession();
    return { sessions: [emptySession], currentSessionId: emptySession.id };
  }
}

export function saveSessionState(sessions: ChatSession[], currentSessionId: string): void {
  const payload = JSON.stringify({ sessions, currentSessionId });
  try {
    localStorage.setItem(STORAGE_KEY, payload);
  } catch {
    // Ignore storage quota/private-mode failures; the current in-memory chat should continue working.
  }
}

export function serializeSessions(sessions: ChatSession[]): string {
  const exported = {
    exportedAt: new Date().toISOString(),
    sessions: visibleSessions(sessions),
  };
  return JSON.stringify(exported, null, 2);
}

export function parseImportedSessions(text: string): ChatSession[] {
  const parsed = JSON.parse(text) as { sessions?: unknown } | unknown[];
  const rawSessions = Array.isArray(parsed) ? parsed : parsed && typeof parsed === "object" ? (parsed as { sessions?: unknown }).sessions : null;
  if (!Array.isArray(rawSessions)) {
    throw new Error("导入文件缺少 sessions 数组。");
  }

  const sessions = rawSessions.map(normalizeSession).filter((session): session is ChatSession => Boolean(session));
  if (sessions.length === 0) {
    throw new Error("导入文件中没有有效会话。");
  }
  return sessions.filter(sessionHasUserMessage);
}
