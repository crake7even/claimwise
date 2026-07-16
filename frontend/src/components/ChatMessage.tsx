import React from "react";
import { Bot, FileText, UserRound } from "lucide-react";
import type { Message } from "../types";

interface ChatMessageProps {
  message: Message;
}

function renderBoldText(content: string) {
  const nodes: React.ReactNode[] = [];
  const pattern = /\*\*([^*]+)\*\*/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(content)) !== null) {
    if (match.index > cursor) {
      nodes.push(content.slice(cursor, match.index));
    }
    nodes.push(
      <strong key={`${match.index}-${match[1]}`} className="font-semibold text-slate-950">
        {match[1]}
      </strong>,
    );
    cursor = match.index + match[0].length;
  }

  if (cursor < content.length) {
    nodes.push(content.slice(cursor));
  }

  return nodes.length > 0 ? nodes : content;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === "user";

  if (message.isLoading) {
    return (
      <div className="flex items-start gap-4">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-700">
          <Bot className="h-4 w-4" />
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm font-medium text-blue-600 shadow-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          正在检索资料，请稍候...
        </div>
      </div>
    );
  }

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-4">
        <div className="max-w-[72%] whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-100 px-5 py-4 text-sm leading-6 text-slate-900">
          {message.content}
        </div>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
          <UserRound className="h-4 w-4" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-700">
        <Bot className="h-4 w-4" />
      </div>
      <div className="max-w-[78%] space-y-3">
        <div className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm leading-6 text-slate-900 shadow-sm">
          {renderBoldText(message.content)}
          {message.isStreaming && (
            <span className="ml-1 inline-block h-4 w-1.5 -mb-0.5 animate-pulse bg-slate-400" />
          )}
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pl-2 text-xs text-slate-500">
            <span className="flex items-center gap-1 font-medium text-slate-600">
              <FileText className="h-3.5 w-3.5" />
              参考资料:
            </span>
            {message.sources.map((source, idx) => (
              <span key={idx} className="font-medium text-blue-700">
                {source}
                {idx < message.sources!.length - 1 ? "、" : ""}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
