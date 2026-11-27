import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { Popover } from "@base-ui/react/popover";
import { Dialog } from "@base-ui/react/dialog";
import { AlertTriangle, Check, ChevronDown, Copy, ExternalLink, FileText, Globe, Search, ShieldCheck, X } from "lucide-react";
import type { Message, RetrievalStage, SearchMode, Source } from "../types";
import { CITATION_PREFIX, citedIds, linkCitations } from "../citations";
import { groupSources, sourceExcerpt, sourceTitle, splitByCitation, type SourceGroup } from "../sourcePresentation";

interface ChatMessageProps {
  message: Message;
  /** 后端是否已连通（health 成功）；未连通时长时间等待才提示"服务唤醒" */
  serviceConnected?: boolean;
  /** 引用卡片的碰撞边界（对话滚动区），使卡片不被底部输入框遮挡 */
  boundary?: HTMLElement | null;
}

const MODE_BADGE: Record<SearchMode, { label: string; className: string }> = {
  quick: { label: "快速检索", className: "bg-amber-50 text-amber-700 ring-amber-200/70" },
  semantic: { label: "语义理解", className: "bg-violet-50 text-violet-700 ring-violet-200/70" },
  web: { label: "联网搜索", className: "bg-sky-50 text-sky-700 ring-sky-200/70" },
};

// 宽度不超过 640px 时，引用卡片改为底部抽屉
const MOBILE_QUERY = "(max-width: 640px)";

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => typeof window !== "undefined" && window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}

function AssistantAvatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm shadow-brand-500/30">
      <ShieldCheck className="h-4 w-4" />
    </div>
  );
}

const STAGE_TEXT: Record<RetrievalStage, string> = {
  rewrite: "正在理解问题…",
  retrieve: "正在检索资料…",
  rerank: "正在筛选相关条款…",
  generate: "正在生成回答…",
};

function loadingText(mode: SearchMode | undefined, slow: boolean, serviceConnected: boolean, stage?: RetrievalStage): string {
  if (slow && !serviceConnected) return "服务可能正在唤醒，首次请求需要 30–60 秒…";
  if (stage === "retrieve" && mode === "web") return "正在检索资料并联网搜索…";
  if (stage) return STAGE_TEXT[stage];
  if (mode === "web") return slow ? "正在整理联网搜索结果…" : "正在检索资料并联网搜索…";
  return slow ? "仍在处理，请稍候…" : "正在检索资料…";
}

function LoadingIndicator({ mode, stage, serviceConnected }: { mode?: SearchMode; stage?: RetrievalStage; serviceConnected: boolean }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), 8000);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="flex items-center gap-3 rounded-2xl bg-white px-5 py-4 text-sm text-slate-500 shadow-soft ring-1 ring-slate-200/60" aria-live="polite">
      <span className="flex items-center gap-1" aria-hidden>
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
        <span className="typing-dot h-1.5 w-1.5 rounded-full bg-brand-500" />
      </span>
      {loadingText(mode, slow, serviceConnected, stage)}
    </div>
  );
}

function OpenLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="ml-auto flex shrink-0 items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700 hover:underline"
    >
      打开原文 <ExternalLink className="h-3 w-3" />
    </a>
  );
}

/** 单条来源的正文：编号 + 条款名 + 摘录 */
function SourceExcerpt({ source, highlighted = false }: { source: Source; highlighted?: boolean }) {
  const excerpt = sourceExcerpt(source);
  return (
    <section data-source-id={source.id} className={`rounded-lg p-2 ${highlighted ? "bg-brand-50/60" : ""}`}>
      <div className="mb-1 flex items-start gap-2 font-medium text-slate-800">
        <span className="shrink-0 text-brand-600">[{source.id}]</span>
        {excerpt.heading && <span className="min-w-0 break-words">{excerpt.heading}</span>}
        {source.url && <OpenLink url={source.url} />}
      </div>
      <p className="whitespace-pre-wrap break-words">{excerpt.text}</p>
    </section>
  );
}

/** 引用卡片内容：文档名在上，正文超长时在卡片内滚动 */
function CitationCard({ source }: { source: Source }) {
  return (
    <>
      <div className="flex items-center gap-1.5 border-b border-slate-100 px-4 py-2.5 text-xs font-semibold text-slate-900">
        {source.kind === "web" ? <Globe className="h-3.5 w-3.5 shrink-0 text-slate-400" /> : <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
        <span className="min-w-0 break-words">{sourceTitle(source)}</span>
      </div>
      <div className="scroll-thin overflow-y-auto px-2 py-1 text-[13px] leading-6 text-slate-600">
        <SourceExcerpt source={source} />
      </div>
    </>
  );
}

const badgeClass =
  "mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px cursor-pointer items-center justify-center rounded-full px-1 align-middle text-[10px] font-semibold transition-colors outline-none focus-visible:ring-2 focus-visible:ring-brand-400 bg-brand-50 text-brand-700 hover:bg-brand-100 data-[popup-open]:bg-brand-600 data-[popup-open]:text-white";

/** 正文角标：桌面端在旁边弹出卡片，小屏为底部抽屉；Esc、点外部、再点角标均可关闭 */
function CitationBadge({ source, isMobile, boundary }: { source: Source; isMobile: boolean; boundary?: HTMLElement | null }) {
  const label = `查看引用 ${source.id}：${sourceTitle(source)}`;
  if (isMobile) {
    return (
      <Dialog.Root>
        <Dialog.Trigger className={badgeClass} aria-label={label}>
          {source.id}
        </Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Backdrop className="fixed inset-0 z-40 bg-slate-900/30 animate-fade" />
          <Dialog.Popup className="fixed inset-x-0 bottom-0 z-50 flex max-h-[70dvh] flex-col rounded-t-2xl bg-white pb-[env(safe-area-inset-bottom)] shadow-float outline-none animate-rise">
            <div className="flex items-center justify-between pt-2 pr-2 pl-4">
              <Dialog.Title className="text-xs font-medium text-slate-500">引用 [{source.id}]</Dialog.Title>
              <Dialog.Close className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100" aria-label="关闭">
                <X className="h-4 w-4" />
              </Dialog.Close>
            </div>
            <CitationCard source={source} />
          </Dialog.Popup>
        </Dialog.Portal>
      </Dialog.Root>
    );
  }
  return (
    <Popover.Root>
      <Popover.Trigger className={badgeClass} aria-label={label}>
        {source.id}
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner
          side="bottom"
          align="start"
          sideOffset={6}
          collisionBoundary={boundary ?? undefined}
          collisionPadding={8}
          className="z-50"
        >
          <Popover.Popup className="flex max-h-[min(360px,var(--available-height))] w-[min(420px,calc(100vw-32px))] flex-col rounded-xl bg-white shadow-float ring-1 ring-slate-200/80 outline-none animate-fade">
            <Popover.Title className="sr-only">引用 [{source.id}]</Popover.Title>
            <CitationCard source={source} />
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  );
}

function SourceChip({ group, cited, selected, onClick }: { group: SourceGroup; cited: Set<number>; selected: boolean; onClick: () => void }) {
  const citedCount = group.sources.filter((source) => cited.has(source.id)).length;
  return (
    <button
      type="button"
      onClick={onClick}
      aria-expanded={selected}
      className={`group flex max-w-full items-center gap-1.5 rounded-full py-1 pr-2.5 pl-2 text-xs transition-all duration-150 active:scale-95 ${
        selected
          ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30"
          : "bg-white text-slate-600 ring-1 ring-slate-200 hover:text-brand-700 hover:ring-brand-200"
      }`}
      title={group.title}
    >
      {group.kind === "web" ? <Globe className="h-3 w-3 shrink-0 opacity-70" /> : <FileText className="h-3 w-3 shrink-0 opacity-70" />}
      <span className="max-w-[11rem] truncate sm:max-w-[15rem]">{group.title}</span>
      <span className={`shrink-0 text-[10px] ${selected ? "text-white/80" : "text-slate-400"}`}>
        {citedCount > 0 && citedCount < group.sources.length ? `${citedCount}/` : ""}
        {group.sources.length} 条
      </span>
    </button>
  );
}

function GroupPanel({ group, cited }: { group: SourceGroup; cited: Set<number> }) {
  const panelRef = useRef<HTMLDivElement>(null);
  // 展开后把面板滚进可视区域，避免停在对话区底部被遮住
  useEffect(() => {
    panelRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [group.key]);
  return (
    <div
      ref={panelRef}
      className="scroll-thin max-h-80 scroll-mb-10 space-y-1 overflow-y-auto rounded-xl bg-white p-2 text-[13px] leading-6 text-slate-600 shadow-soft ring-1 ring-slate-200/70 animate-fade"
    >
      <div className="flex items-center gap-2 px-2 pt-1 text-xs font-semibold text-slate-900">
        <span className="min-w-0 break-words">{group.title}</span>
        {group.kind === "web" && group.url && <OpenLink url={group.url} />}
      </div>
      {group.sources.map((source) => (
        <SourceExcerpt key={source.id} source={source} highlighted={cited.has(source.id)} />
      ))}
    </div>
  );
}

function ChipRow({
  groups,
  cited,
  activeKey,
  onToggle,
}: {
  groups: SourceGroup[];
  cited: Set<number>;
  activeKey: string | null;
  onToggle: (key: string) => void;
}) {
  const active = groups.find((group) => group.key === activeKey);
  return (
    <>
      <div className="flex flex-wrap items-center gap-1.5">
        {groups.map((group) => (
          <SourceChip key={group.key} group={group} cited={cited} selected={group.key === activeKey} onClick={() => onToggle(group.key)} />
        ))}
      </div>
      {active && <GroupPanel group={active} cited={cited} />}
    </>
  );
}

function SourceList({ sources, cited, rewritten }: { sources: Source[]; cited: Set<number>; rewritten?: string }) {
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const [showOthers, setShowOthers] = useState(false);
  const groups = useMemo(() => groupSources(sources), [sources]);
  const split = splitByCitation(groups, cited);
  const hasCitations = split.cited.length > 0;
  const toggle = (key: string) => setActiveKey((current) => (current === key ? null : key));

  return (
    <div className="space-y-2">
      {rewritten && (
        <p className="flex items-start gap-1.5 text-xs leading-5 text-slate-500">
          <Search className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 break-words">检索用语：{rewritten}</span>
        </p>
      )}
      {hasCitations ? (
        <>
          <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
            <FileText className="h-3.5 w-3.5" />
            引用资料 · {split.cited.length}
          </div>
          <ChipRow groups={split.cited} cited={cited} activeKey={activeKey} onToggle={toggle} />
          {split.others.length > 0 && (
            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setShowOthers((value) => !value)}
                aria-expanded={showOthers}
                className="flex items-center gap-1 text-xs font-medium text-slate-400 transition-colors hover:text-slate-600"
              >
                <ChevronDown className={`h-3.5 w-3.5 transition-transform ${showOthers ? "" : "-rotate-90"}`} />
                其他检索结果 · {split.others.length}
              </button>
              {showOthers && <ChipRow groups={split.others} cited={cited} activeKey={activeKey} onToggle={toggle} />}
            </div>
          )}
        </>
      ) : (
        <>
          <div className="flex items-center gap-1 text-xs font-medium text-slate-500">
            <Search className="h-3.5 w-3.5" />
            检索结果 · {groups.length}
          </div>
          <ChipRow groups={groups} cited={cited} activeKey={activeKey} onToggle={toggle} />
        </>
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

export const ChatMessage: React.FC<ChatMessageProps> = ({ message, serviceConnected = true, boundary }) => {
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const sources = useMemo(() => message.sources ?? [], [message.sources]);
  const sourceIds = useMemo(() => sources.map((source) => source.id), [sources]);
  const cited = useMemo(() => citedIds(message.content, sourceIds), [message.content, sourceIds]);
  // 组件映射需保持引用稳定，否则父组件重渲染时角标会被重新挂载、已打开的卡片随之关闭
  const markdownComponents = useMemo<Components>(() => ({
    a: ({ href, children }) => {
      if (href?.startsWith(CITATION_PREFIX)) {
        const id = Number(href.slice(CITATION_PREFIX.length));
        const source = sources.find((item) => item.id === id);
        if (source) return <CitationBadge source={source} isMobile={isMobile} boundary={boundary} />;
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand-600 underline underline-offset-2">
          {children}
        </a>
      );
    },
  }), [sources, isMobile, boundary]);
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex animate-rise justify-end">
        <div className="max-w-[88%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-md bg-brand-600 px-4 py-2.5 text-[15px] leading-7 text-white shadow-sm shadow-brand-600/20 sm:max-w-[75%]">
          {message.content}
        </div>
      </div>
    );
  }

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
          <LoadingIndicator mode={message.mode} stage={message.stage} serviceConnected={serviceConnected} />
        ) : (message.content || message.isStreaming) && (
          <div className="markdown-body break-words rounded-2xl rounded-tl-md bg-white px-4 py-3.5 shadow-soft ring-1 ring-slate-200/60 sm:px-5 sm:py-4">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
              {linkCitations(message.content, sourceIds)}
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
        {sources.length > 0 && <SourceList sources={sources} cited={cited} rewritten={message.rewritten} />}
        {finished && message.content && (
          <div className="-ml-2 flex animate-fade items-center">
            <CopyButton text={message.content} />
          </div>
        )}
      </div>
    </div>
  );
};
