import React, { useEffect, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Bot, ExternalLink, FileText, Globe, UserRound } from "lucide-react";
import type { Message, Source } from "../types";

interface ChatMessageProps {
  message: Message;
}

const CITATION_PREFIX = "#cite-";

/** 把正文里的 [1] / [2][3] 转成 Markdown 链接，交给自定义 a 组件渲染为可点击的引用标记。 */
function linkCitations(content: string, sources: Source[]): string {
  const ids = new Set(sources.map((source) => source.id));
  return content.replace(/\[(\d{1,2})\](?!\()/g, (match, raw: string) =>
    ids.has(Number(raw)) ? `[${raw}](${CITATION_PREFIX}${raw})` : match,
  );
}

function LoadingBubble() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 8000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 text-sm font-medium text-blue-600 shadow-sm">
      <span className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
      {slow ? "服务可能正在唤醒，首次请求需要 30–60 秒，请稍候..." : "正在检索资料，请稍候..."}
    </div>
  );
}

function SourceList({
  sources,
  activeId,
  onToggle,
}: {
  sources: Source[];
  activeId: number | null;
  onToggle: (id: number) => void;
}) {
  const active = sources.find((source) => source.id === activeId);
  return (
    <div className="space-y-2 pl-1">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="flex items-center gap-1 font-medium text-slate-600">
          <FileText className="h-3.5 w-3.5" />
          参考资料
        </span>
        {sources.map((source) => (
          <button
            key={source.id}
            type="button"
            onClick={() => onToggle(source.id)}
            className={`flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-left transition-colors ${
              source.id === activeId
                ? "border-blue-300 bg-blue-50 text-blue-700"
                : "border-slate-200 bg-white text-slate-600 hover:border-blue-200 hover:text-blue-700"
            }`}
            title={source.section ? `${source.title} · ${source.section}` : source.title}
          >
            <span className="font-semibold">[{source.id}]</span>
            {source.kind === "web" && <Globe className="h-3 w-3 shrink-0" />}
            <span className="max-w-[12rem] truncate">{source.title}</span>
          </button>
        ))}
      </div>
      {active && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-5 text-slate-700">
          <div className="mb-1 flex flex-wrap items-center gap-x-2 font-semibold text-slate-900">
            <span>[{active.id}] {active.title}</span>
            {active.section && <span className="font-normal text-slate-500">{active.section}</span>}
            {active.url && (
              <a
                href={active.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 font-normal text-blue-700 hover:underline"
              >
                打开原文 <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <p className="max-h-48 overflow-y-auto whitespace-pre-wrap">{active.snippet}</p>
        </div>
      )}
    </div>
  );
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [activeSource, setActiveSource] = useState<number | null>(null);
  const isUser = message.role === "user";
  const sources = message.sources ?? [];

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 sm:gap-4">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-xl border border-slate-200 bg-slate-100 px-4 py-3 text-sm leading-6 text-slate-900 sm:max-w-[72%] sm:px-5 sm:py-4">
          {message.content}
        </div>
        <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600 sm:flex">
          <UserRound className="h-4 w-4" />
        </div>
      </div>
    );
  }

  const toggleSource = (id: number) => setActiveSource((current) => (current === id ? null : id));
  const markdownComponents: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITATION_PREFIX)) {
        const id = Number(href.slice(CITATION_PREFIX.length));
        return (
          <button
            type="button"
            onClick={() => toggleSource(id)}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded bg-blue-50 px-1 align-text-top text-[11px] font-semibold text-blue-700 hover:bg-blue-100"
          >
            {id}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-700 underline">
          {children}
        </a>
      );
    },
  };

  return (
    <div className="flex items-start gap-3 sm:gap-4">
      <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-50 text-blue-700 sm:flex">
        <Bot className="h-4 w-4" />
      </div>
      <div className="min-w-0 max-w-full flex-1 space-y-3 sm:max-w-[78%] sm:flex-none">
        {message.isLoading ? (
          <LoadingBubble />
        ) : (
          <div className="markdown-body break-words rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 shadow-sm sm:px-5 sm:py-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {linkCitations(message.content, sources)}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="ml-1 inline-block h-4 w-1.5 -mb-0.5 animate-pulse bg-slate-400" />
            )}
          </div>
        )}
        {message.error && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {message.error}
          </div>
        )}
        {sources.length > 0 && <SourceList sources={sources} activeId={activeSource} onToggle={toggleSource} />}
      </div>
    </div>
  );
};
