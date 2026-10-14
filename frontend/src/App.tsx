import React, { useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import type { ChatSession, HealthStatus, Message, SearchMode } from "./types";
import { ApiError, describeError, fetchHealth, streamChat, type HistoryTurn } from "./api";
import {
  createEmptySession,
  createId,
  loadSessionState,
  parseImportedSessions,
  refreshSession,
  saveSessionState,
  serializeSessions,
  sessionHasUserMessage,
  visibleSessions,
} from "./sessionHistory";
import { ArrowDown, BookOpenCheck, Globe, Menu, ShieldCheck, Sparkles, Zap } from "lucide-react";

const suggestions: Array<{ text: string; mode: SearchMode; tag: string; icon: typeof Zap; tone: string }> = [
  { text: "介绍下雇主责任险的保障范围", mode: "quick", tag: "快速检索", icon: Zap, tone: "text-amber-600 bg-amber-50" },
  { text: "员工喝酒开车出事，意外险赔吗？", mode: "semantic", tag: "语义理解", icon: Sparkles, tone: "text-violet-600 bg-violet-50" },
  { text: "施工保对投保工程有什么要求？", mode: "semantic", tag: "语义理解", icon: Sparkles, tone: "text-violet-600 bg-violet-50" },
  { text: "保险行业 AI 最新动态", mode: "web", tag: "联网搜索", icon: Globe, tone: "text-sky-600 bg-sky-50" },
];

// 多轮对话最多携带的历史消息条数（用户与助手各算一条）
const HISTORY_MESSAGES = 6;
// 流式输出时合并渲染的间隔，避免每个分片都触发一次整页重渲染
const STREAM_FLUSH_MS = 60;
const HEALTH_RETRY_MS = 10000;

interface SessionState {
  sessions: ChatSession[];
  currentSessionId: string;
}

function buildHistory(messages: Message[]): HistoryTurn[] {
  return messages
    .filter((message) => !message.isLoading && !message.isStreaming && message.content.trim())
    .slice(-HISTORY_MESSAGES)
    .map((message) => ({ role: message.role === "user" ? "user" : "assistant", content: message.content }));
}

export default function App() {
  const [sessionState, setSessionState] = useState<SessionState>(() => loadSessionState());
  const [isProcessing, setIsProcessing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);
  const [showJump, setShowJump] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const { sessions, currentSessionId } = sessionState;
  const currentSession = sessions.find((session) => session.id === currentSessionId) ?? sessions[0];
  const currentMessages = currentSession?.messages ?? [];
  const sidebarSessions = useMemo(() => visibleSessions(sessions), [sessions]);

  // 未连通时每 10 秒探测一次后端（冷启动唤醒、本地服务重启后自动恢复"服务在线"）
  useEffect(() => {
    if (health) return;
    let cancelled = false;
    const probe = () =>
      fetchHealth().then((result) => {
        if (!cancelled && result) setHealth(result);
      });
    probe();
    const timer = window.setInterval(probe, HEALTH_RETRY_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [health]);

  // 流式输出期间不写 localStorage，结束后统一保存一次
  useEffect(() => {
    if (!isProcessing) saveSessionState(sessions, currentSessionId);
  }, [sessions, currentSessionId, isProcessing]);

  // 仅当用户停留在底部附近时自动跟随滚动，向上翻阅历史时不打断
  useEffect(() => {
    const container = scrollRef.current;
    if (container && stickToBottomRef.current) {
      container.scrollTop = container.scrollHeight;
    }
  }, [currentMessages]);

  useEffect(() => {
    stickToBottomRef.current = true;
  }, [currentSessionId]);

  const handleScroll = () => {
    const container = scrollRef.current;
    if (!container) return;
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
    stickToBottomRef.current = nearBottom;
    setShowJump(!nearBottom);
  };

  const scrollToBottom = () => {
    const container = scrollRef.current;
    if (!container) return;
    stickToBottomRef.current = true;
    setShowJump(false);
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  };

  const updateSessionMessages = (sessionId: string, updater: (messages: Message[]) => Message[]) => {
    setSessionState((prev) => ({
      ...prev,
      sessions: prev.sessions.map((session) =>
        session.id === sessionId ? refreshSession(session, updater(session.messages)) : session,
      ),
    }));
  };

  const handleNewChat = () => {
    setNotice(null);
    setMobileSidebarOpen(false);
    setSessionState((prev) => {
      const existingEmptySession = prev.sessions.find((session) => !sessionHasUserMessage(session) && session.messages.length === 0);
      if (existingEmptySession) {
        return { ...prev, currentSessionId: existingEmptySession.id };
      }

      const emptySession = createEmptySession();
      return {
        sessions: [emptySession, ...prev.sessions],
        currentSessionId: emptySession.id,
      };
    });
  };

  const handleSelectSession = (sessionId: string) => {
    setNotice(null);
    setMobileSidebarOpen(false);
    setSessionState((prev) => ({ ...prev, currentSessionId: sessionId }));
  };

  const handleDeleteSession = (sessionId: string) => {
    const target = sessions.find((session) => session.id === sessionId);
    if (!window.confirm(`确定删除会话“${target?.title ?? ""}”吗？删除后无法恢复。`)) return;
    setNotice(null);
    setSessionState((prev) => {
      let remainingSessions = prev.sessions.filter((session) => session.id !== sessionId);
      if (remainingSessions.length === 0) {
        const emptySession = createEmptySession();
        return { sessions: [emptySession], currentSessionId: emptySession.id };
      }

      if (prev.currentSessionId !== sessionId) {
        return { ...prev, sessions: remainingSessions };
      }

      const nextCurrent = visibleSessions(remainingSessions)[0] ?? remainingSessions[0];
      if (!nextCurrent) {
        const emptySession = createEmptySession();
        remainingSessions = [emptySession];
        return { sessions: remainingSessions, currentSessionId: emptySession.id };
      }

      return { sessions: remainingSessions, currentSessionId: nextCurrent.id };
    });
  };

  const handleExport = () => {
    setNotice(null);
    const content = serializeSessions(sessions);
    const exportedCount = visibleSessions(sessions).length;
    if (exportedCount === 0) {
      setNotice("暂无可导出的历史会话。");
      return;
    }

    const blob = new Blob([content], { type: "application/json;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `insurance-chat-history-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    // 部分浏览器在 click 后异步开始下载，立即释放会导致下载失败
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  const handleImport = async (file: File) => {
    try {
      const text = await file.text();
      const importedSessions = parseImportedSessions(text);

      setSessionState((prev) => {
        const existingIds = new Set(prev.sessions.map((session) => session.id));
        const mergedImports = importedSessions.map((session) =>
          existingIds.has(session.id) ? { ...session, id: createId() } : session,
        );
        return {
          sessions: [...mergedImports, ...prev.sessions],
          currentSessionId: mergedImports[0]?.id ?? prev.currentSessionId,
        };
      });
      setNotice(`已导入 ${importedSessions.length} 个历史会话。`);
    } catch (error) {
      setNotice(error instanceof Error ? `导入失败：${error.message}` : "导入失败：文件格式不正确。");
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const handleSend = async (text: string, mode: SearchMode) => {
    if (!text.trim() || isProcessing || !currentSession) return;

    const sessionId = currentSession.id;
    const history = buildHistory(currentSession.messages);
    const userMessage: Message = { id: createId(), role: "user", content: text };
    const aiMessageId = createId();
    const aiMessage: Message = { id: aiMessageId, role: "ai", content: "", isLoading: true, mode };
    const patchAiMessage = (patch: Partial<Message>) =>
      updateSessionMessages(sessionId, (messages) =>
        messages.map((message) => (message.id === aiMessageId ? { ...message, ...patch } : message)),
      );

    setNotice(null);
    stickToBottomRef.current = true;
    updateSessionMessages(sessionId, (messages) => [...messages, userMessage, aiMessage]);
    setIsProcessing(true);

    const controller = new AbortController();
    abortRef.current = controller;
    let content = "";
    let flushTimer: number | undefined;
    const flush = () => {
      flushTimer = undefined;
      patchAiMessage({ content, isLoading: false, isStreaming: true });
    };

    try {
      await streamChat(
        { message: text, mode, history },
        {
          onSources: (sources) => patchAiMessage({ sources }),
          onDelta: (delta) => {
            content += delta;
            if (flushTimer === undefined) flushTimer = window.setTimeout(flush, STREAM_FLUSH_MS);
          },
          onError: (message) => patchAiMessage({ error: message }),
        },
        controller.signal,
      );
      window.clearTimeout(flushTimer);
      patchAiMessage({ content: content || "没有获取到回答，请稍后重试。", isLoading: false, isStreaming: false });
    } catch (error) {
      window.clearTimeout(flushTimer);
      if (controller.signal.aborted) {
        patchAiMessage({ content: content || "已停止生成。", isLoading: false, isStreaming: false, error: content ? "已手动停止生成，回答可能不完整。" : undefined });
      } else {
        patchAiMessage({ content, isLoading: false, isStreaming: false, error: describeError(error) });
        // 连接失败或网关 5xx（含本地代理在后端未启动时的 500）时，状态标记回"连接中"，由探测逻辑自动重连
        if (error instanceof TypeError || (error instanceof ApiError && (error.status ?? 0) >= 500)) setHealth(null);
      }
    } finally {
      abortRef.current = null;
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-canvas font-sans text-slate-900">
      <Sidebar
        collapsed={sidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onToggle={() => setSidebarCollapsed((value) => !value)}
        onNewChat={handleNewChat}
        sessions={sidebarSessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onExport={handleExport}
        onImport={handleImport}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-200/70 bg-white/80 px-4 backdrop-blur sm:px-6">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            className="-ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition-colors hover:bg-slate-100 md:hidden"
            title="打开会话列表"
          >
            <Menu className="h-5 w-5" />
          </button>
          <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold text-slate-900">
            {currentMessages.length > 0 ? currentSession?.title : "保险资料智能问答"}
          </h1>
          <span
            className={`flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1 ${
              health ? "bg-emerald-50 text-emerald-700 ring-emerald-200/70" : "bg-slate-50 text-slate-500 ring-slate-200"
            }`}
            title={health ? "后端服务已连接" : "正在连接后端服务，首次访问可能需要唤醒"}
          >
            <span className={`h-1.5 w-1.5 rounded-full ${health ? "bg-emerald-500" : "animate-pulse bg-slate-400"}`} />
            {health ? "服务在线" : "连接中"}
          </span>
        </header>

        <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          <div ref={scrollRef} onScroll={handleScroll} className="scroll-thin min-h-0 flex-1 overflow-y-auto px-4 sm:px-6">
            <div className="mx-auto flex w-full max-w-[760px] flex-col gap-6 py-6 sm:py-10">
              {notice && (
                <div className="animate-fade rounded-xl bg-brand-50 px-4 py-3 text-sm text-brand-800 ring-1 ring-brand-100">{notice}</div>
              )}

              {currentMessages.length === 0 ? (
                <div className="flex animate-rise flex-col items-center pt-4 text-center sm:pt-12">
                  <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-lg shadow-brand-500/30">
                    <ShieldCheck className="h-7 w-7" />
                  </div>
                  <h2 className="mt-5 text-2xl font-semibold tracking-tight text-slate-900 sm:text-[28px]">有什么保险问题想问？</h2>
                  <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">
                    基于雇主责任险、团体意外险、施工保等产品资料作答，每个结论都标注原文出处。
                  </p>
                  <div className="mt-8 grid w-full grid-cols-1 gap-2.5 text-left sm:grid-cols-2 sm:gap-3">
                    {suggestions.map(({ text, mode, tag, icon: Icon, tone }) => (
                      <button
                        key={text}
                        type="button"
                        onClick={() => handleSend(text, mode)}
                        className="group flex items-start gap-3 rounded-2xl bg-white p-4 text-left shadow-soft ring-1 ring-slate-200/70 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-float hover:ring-brand-200 active:translate-y-0"
                      >
                        <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${tone}`}>
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0">
                          <span className="block text-sm font-medium leading-6 text-slate-800 group-hover:text-brand-700">{text}</span>
                          <span className="mt-0.5 block text-xs text-slate-400">{tag}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="mt-8 flex flex-wrap justify-center gap-x-5 gap-y-2 text-xs text-slate-400">
                    <span className="flex items-center gap-1.5"><BookOpenCheck className="h-3.5 w-3.5" />引用可溯源</span>
                    <span className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5" />支持多轮追问</span>
                    <span className="flex items-center gap-1.5"><Globe className="h-3.5 w-3.5" />可联网补充</span>
                  </div>
                </div>
              ) : (
                currentMessages.map((msg) => <ChatMessage key={msg.id} message={msg} serviceConnected={health !== null} />)
              )}
            </div>
          </div>

          {showJump && currentMessages.length > 0 && (
            <button
              type="button"
              onClick={scrollToBottom}
              className="absolute bottom-[132px] left-1/2 z-10 flex h-9 w-9 -translate-x-1/2 animate-fade items-center justify-center rounded-full bg-white text-slate-600 shadow-float ring-1 ring-slate-200 transition-colors hover:text-brand-700"
              title="回到底部"
            >
              <ArrowDown className="h-4 w-4" />
            </button>
          )}

          <div className="relative shrink-0 px-3 pt-2 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-6 sm:pb-5">
            <div className="pointer-events-none absolute inset-x-0 -top-8 h-8 bg-gradient-to-t from-canvas to-transparent" />
            <div className="mx-auto w-full max-w-[760px]">
              <ChatInput onSend={handleSend} onStop={handleStop} isProcessing={isProcessing} health={health} />
              <p className="mt-2 text-center text-[11px] text-slate-400">AI 生成内容仅供参考，不作为最终承保或理赔结论。</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
