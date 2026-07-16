export type SearchMode = "quick" | "semantic" | "web";

export interface Message {
  id: string;
  role: "user" | "ai";
  content: string;
  mode?: SearchMode;
  isStreaming?: boolean;
  isLoading?: boolean;
  sources?: string[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}
