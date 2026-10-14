import React, { useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import type { ChatSession, HealthStatus, Message, SearchMode } from "./types";
import { describeError, fetchHealth, streamChat, type HistoryTurn } from "./api";
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
import { Menu } from "lucide-react";

const welcomeMessage: Message = {
  id: "welcome",
  role: "ai",
  content:
    "您好！我是您的保险资料智能问答助手。您可以直接向我提问关于保险产品、保障范围、理赔流程等方面的问题。回答会标注引用编号，点击即可查看原文依据。\n\n请问今天有什么我可以帮您的？",
};

const suggestions: Array<{ text: string; mode: SearchMode }> = [
  { text: "介绍下雇主责任险", mode: "quick" },
  { text: "员工喝酒开车出事，意外险赔吗？", mode: "semantic" },
  { text: "搜索保险行业 AI 最新新闻", mode: "web" },
];

// 多轮对话最多携带的历史消息条数（用户与助手各算一条）
const HISTORY_MESSAGES = 6;
// 流式输出时合并渲染的间隔，避免每个分片都触发一次整页重渲染
const STREAM_FLUSH_MS = 60;

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
  const abortRef = useRef<AbortController | null>(null);

  const { sessions, currentSessionId } = sessionState;
  const currentSession = sessions.find((session) => session.id === currentSessionId) ?? sessions[0];
  const currentMessages = currentSession?.messages ?? [];
  const sidebarSessions = useMemo(() => visibleSessions(sessions), [sessions]);
  const displayedMessages = useMemo(() => [welcomeMessage, ...currentMessages], [currentMessages]);

  useEffect(() => {
    fetchHealth().then(setHealth);
  }, []);

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
  }, [displayedMessages]);

  useEffect(() => {
    stickToBottomRef.current = true;
  }, [currentSessionId]);

  const handleScroll = () => {
    const container = scrollRef.current;
    if (!container) return;
    stickToBottomRef.current = container.scrollHeight - container.scrollTop - container.clientHeight < 80;
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
      }
    } finally {
      abortRef.current = null;
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-[#f8f9fb] font-sans text-slate-900">
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

      <main className="flex min-w-0 flex-1 flex-col transition-all duration-300">
        <header className="flex h-[64px] shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 sm:h-[74px] sm:px-6">
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 md:hidden"
            title="打开会话列表"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-bold leading-6 text-slate-950 sm:text-xl">保险资料智能问答系统</h1>
            <p className="mt-0.5 hidden text-sm text-slate-500 sm:block">面向业务人员的专业保险知识库助手</p>
          </div>
        </header>

        <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-[#f6f7f9]">
          <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-8 sm:py-8">
            <div className="mx-auto flex w-full max-w-[980px] flex-col gap-5">
              {notice && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700 sm:ml-14">
                  {notice}
                </div>
              )}

              {displayedMessages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {currentMessages.length === 0 && (
                <div className="grid grid-cols-1 gap-3 sm:ml-14 sm:grid-cols-3 sm:gap-4">
                  {suggestions.map((item) => (
                    <button
                      key={item.text}
                      onClick={() => handleSend(item.text, item.mode)}
                      className="min-h-14 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium leading-5 text-slate-800 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                    >
                      {item.text}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="shrink-0 border-t border-slate-200 bg-white/72 px-3 py-3 backdrop-blur sm:px-8 sm:py-4">
            <div className="mx-auto w-full max-w-[980px]">
              <ChatInput onSend={handleSend} onStop={handleStop} isProcessing={isProcessing} health={health} />
              <p className="mt-2 text-center text-xs text-slate-500 sm:mt-3">
                AI 生成的内容仅供参考，不作为最终承保或理赔结论。
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
