export type SearchMode = "quick" | "semantic" | "web";

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
