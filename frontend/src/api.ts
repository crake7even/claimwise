import type { HealthStatus, RetrievalStage, SearchMode, Source } from "./types";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export interface HistoryTurn {
  role: "user" | "assistant";
  content: string;
}

interface StreamHandlers {
  onSources: (sources: Source[], rewritten: string | null) => void;
  onStage: (stage: RetrievalStage) => void;
  onDelta: (text: string) => void;
  onError: (message: string) => void;
}

type StreamEvent =
  | { type: "stage"; stage: RetrievalStage }
  | { type: "sources"; sources: Source[]; rewritten?: string | null }
  | { type: "delta"; text: string }
  | { type: "error"; message: string }
  | { type: "done" };

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
  }
}

export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) return "请求过于频繁，请稍后再试。";
    if (error.status && error.status >= 500) return `服务暂时不可用（${error.status}），请稍后重试。`;
    return error.message;
  }
  if (error instanceof TypeError) {
    return "无法连接到问答服务。在线 Demo 的后端空闲后会休眠，首次访问需要 30–60 秒唤醒，请稍后重试。";
  }
  return error instanceof Error ? error.message : "请求失败，请稍后重试。";
}

/** 读取后端 NDJSON 事件流：stage* → sources → stage → delta* → done，error 事件可能出现在任意位置；未知事件类型忽略。 */
export async function streamChat(
  body: { message: string; mode: SearchMode; history: HistoryTurn[] },
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(`请求失败：${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let completed = false;
  const handleLine = (line: string) => {
    if (completed || !line.trim()) return;
    const event = JSON.parse(line) as StreamEvent;
    if (event.type === "stage") handlers.onStage(event.stage);
    else if (event.type === "sources") handlers.onSources(event.sources, event.rewritten ?? null);
    else if (event.type === "delta") handlers.onDelta(event.text);
    else if (event.type === "error") handlers.onError(event.message);
    else if (event.type === "done") completed = true;
  };

  try {
    while (!completed) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(handleLine);
    }
    buffer += decoder.decode();
    handleLine(buffer);
    if (!completed) throw new ApiError("回答接收中断，内容可能不完整，请重试。");
  } catch (error) {
    if (signal.aborted || error instanceof ApiError) throw error;
    throw new ApiError("回答接收中断，内容可能不完整，请重试。");
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export async function fetchHealth(): Promise<HealthStatus | null> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/health`);
    if (!response.ok) return null;
    const data = (await response.json()) as Partial<HealthStatus>;
    return { quick: Boolean(data.quick), semantic: Boolean(data.semantic), web: Boolean(data.web) };
  } catch {
    return null;
  }
}
