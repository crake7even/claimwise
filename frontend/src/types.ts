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
