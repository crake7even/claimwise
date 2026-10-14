import React, { useEffect, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Check, Copy, ExternalLink, FileText, Globe, ShieldCheck } from "lucide-react";
import type { Message, SearchMode, Source } from "../types";

interface ChatMessageProps {
  message: Message;
  /** 后端是否已连通（health 成功）；未连通时长时间等待才提示"服务唤醒" */
  serviceConnected?: boolean;
}

const CITATION_PREFIX = "#cite-";

const MODE_BADGE: Record<SearchMode, { label: string; className: string }> = {
  quick: { label: "快速检索", className: "bg-amber-50 text-amber-700 ring-amber-200/70" },
  semantic: { label: "语义理解", className: "bg-violet-50 text-violet-700 ring-violet-200/70" },
  web: { label: "联网搜索", className: "bg-sky-50 text-sky-700 ring-sky-200/70" },
};

/** 把正文里的 [1] / [2][3] 转成 Markdown 链接，交给自定义 a 组件渲染为可点击的引用标记。 */
function linkCitations(content: string, sources: Source[]): string {
  const ids = new Set(sources.map((source) => source.id));
  return content.replace(/\[(\d{1,2})\](?!\()/g, (match, raw: string) =>
    ids.has(Number(raw)) ? `[${raw}](${CITATION_PREFIX}${raw})` : match,
  );
}

function AssistantAvatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm shadow-brand-500/30">
      <ShieldCheck className="h-4 w-4" />
    </div>
  );
}

function loadingText(mode: SearchMode | undefined, slow: boolean, serviceConnected: boolean): string {
  if (slow && !serviceConnected) return "服务可能正在唤醒，首次请求需要 30–60 秒…";
  if (mode === "web") return slow ? "正在整理联网搜索结果…" : "正在检索资料并联网搜索…";
  return slow ? "仍在处理，请稍候…" : "正在检索资料…";
}

function LoadingIndicator({ mode, serviceConnected }: { mode?: SearchMode; serviceConnected: boolean }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 8000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm text-slate-500 shadow-soft ring-1 ring-slate-200/60">
      <span className="flex items-center gap-1" aria-hidden>
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
      </span>
      {loadingText(mode, slow, serviceConnected)}
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
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="mr-1 flex items-center gap-1 text-xs font-medium text-slate-500">
          <FileText className="h-3.5 w-3.5" />
          参考资料 · {sources.length}
        </span>
        {sources.map((source) => {
          const selected = source.id === activeId;
          return (
            <button
              key={source.id}
              type="button"
              onClick={() => onToggle(source.id)}
              aria-pressed={selected}
              className={`group flex max-w-full items-center gap-1.5 rounded-full py-1 pr-2.5 pl-1 text-xs transition-all duration-150 active:scale-95 ${
                selected
                  ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
                  : "bg-white text-slate-600 ring-1 ring-slate-200 hover:text-brand-700 hover:ring-brand-200"
              }`}
              title={source.section ? `${source.title} · ${source.section}` : source.title}
            >
              <span
                className={`flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-semibold ${
                  selected ? "bg-white/20" : "bg-slate-100 text-slate-500 group-hover:bg-brand-50 group-hover:text-brand-700"
                }`}
              >
                {source.id}
              </span>
              {source.kind === "web" && <Globe className="h-3 w-3 shrink-0 opacity-70" />}
              <span className="max-w-[10rem] truncate sm:max-w-[13rem]">{source.title}</span>
            </button>
          );
        })}
      </div>
      {active && (
        <div key={active.id} className="animate-fade rounded-xl bg-white p-4 text-[13px] leading-6 text-slate-600 shadow-soft ring-1 ring-slate-200/70">
          <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-slate-900">
              [{active.id}] {active.title}
            </span>
            {active.section && (
              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">{active.section}</span>
            )}
            {active.url && (
              <a
                href={active.url}
                target="_blank"
                rel="noopener noreferrer"
                className="ml-auto flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
              >
                打开原文 <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <p className="scroll-thin max-h-52 overflow-y-auto whitespace-pre-wrap">{active.snippet}</p>
        </div>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // 剪贴板不可用（如非 HTTPS）时静默忽略
    }
  };
  return (
    <button
      type="button"
      onClick={handleCopy}
      className="flex h-7 items-center gap-1 rounded-md px-2 text-xs text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
      title="复制回答"
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? "已复制" : "复制"}
    </button>
  );
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, serviceConnected = true }) => {
  const [activeSource, setActiveSource] = useState<number | null>(null);
  const isUser = message.role === "user";
  const sources = message.sources ?? [];

  if (isUser) {
    return (
      <div className="flex animate-rise justify-end">
        <div className="max-w-[88%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-md bg-brand-600 px-4 py-2.5 text-[15px] leading-7 text-white shadow-sm shadow-brand-600/20 sm:max-w-[75%]">
          {message.content}
        </div>
      </div>
    );
  }

  const toggleSource = (id: number) => setActiveSource((current) => (current === id ? null : id));
  const markdownComponents: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith(CITATION_PREFIX)) {
        const id = Number(href.slice(CITATION_PREFIX.length));
        const source = sources.find((item) => item.id === id);
        return (
          <button
            type="button"
            onClick={() => toggleSource(id)}
            title={source ? `${source.title}${source.section ? ` · ${source.section}` : ""}` : undefined}
            className={`mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-full px-1 align-middle text-[10px] font-semibold transition-colors ${
              id === activeSource ? "bg-brand-600 text-white" : "bg-brand-50 text-brand-700 hover:bg-brand-100"
            }`}
          >
            {id}
          </button>
        );
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline underline-offset-2">
          {children}
        </a>
      );
    },
  };

  const badge = message.mode ? MODE_BADGE[message.mode] : null;
  const finished = !message.isLoading && !message.isStreaming && message.id !== "welcome";

  return (
    <div className="animate-rise space-y-2.5">
      {/* 手机上头像与标签同行、正文占满宽度；桌面端正文与头像右侧对齐 */}
      <div className="flex h-8 items-center gap-2.5 text-xs">
        <AssistantAvatar />
        <span className="font-semibold text-slate-700">ClaimWise</span>
        {badge && <span className={`rounded-full px-2 py-0.5 font-medium ring-1 ${badge.className}`}>{badge.label}</span>}
      </div>
      <div className="min-w-0 space-y-2.5 sm:pl-[42px]">
        {message.isLoading ? (
          <LoadingIndicator mode={message.mode} serviceConnected={serviceConnected} />
        ) : (message.content || message.isStreaming) && (
          <div className="markdown-body break-words rounded-2xl rounded-tl-md bg-white px-4 py-3.5 shadow-soft ring-1 ring-slate-200/60 sm:px-5 sm:py-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {linkCitations(message.content, sources)}
            </ReactMarkdown>
            {message.isStreaming && (
              <span className="ml-0.5 inline-block h-4 w-[3px] translate-y-0.5 animate-pulse rounded-full bg-brand-500" />
            )}
          </div>
        )}
        {message.error && (
          <div className="flex animate-fade items-start gap-2 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800 ring-1 ring-amber-200/70">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {message.error}
          </div>
        )}
        {sources.length > 0 && <SourceList sources={sources} activeId={activeSource} onToggle={toggleSource} />}
        {finished && message.content && (
          <div className="-ml-2 flex animate-fade items-center">
            <CopyButton text={message.content} />
          </div>
        )}
      </div>
    </div>
  );
};
