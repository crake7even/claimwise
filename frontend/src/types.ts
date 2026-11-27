export type SearchMode = "quick" | "semantic" | "web";

/** 后端 stage 事件：查询改写 / 召回 / 重排 / 生成 */
export type RetrievalStage = "rewrite" | "retrieve" | "rerank" | "generate";

export interface Source {
  id: number;
  kind: "local" | "web";
  title: string;
  section?: string;
  snippet: string;
  url?: string;
  score?: number | null;
}

export interface Message {
  id: string;
  role: "user" | "ai";
  content: string;
  mode?: SearchMode;
  isStreaming?: boolean;
  isLoading?: boolean;
  sources?: Source[];
  /** 检索实际使用的改写查询；与原问题相同或未改写时为空 */
  rewritten?: string;
  /** 仅流式过程中使用，不持久化 */
  stage?: RetrievalStage;
  error?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export interface HealthStatus {
  quick: boolean;
  semantic: boolean;
  web: boolean;
}
