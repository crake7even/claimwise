import React, { useEffect, useMemo, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import type { ChatSession, Message, SearchMode } from "./types";
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
import { MessageSquarePlus } from "lucide-react";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const welcomeMessage: Message = {
  id: "welcome",
  role: "ai",
  content:
    "您好！我是您的保险资料智能问答助手。您可以直接向我提问关于保险产品、保障范围、理赔流程等方面的问题。默认会优先从本地资料库中为您检索准确的信息。\n\n请问今天有什么我可以帮您的？",
};

const suggestions: Array<{ text: string; mode: SearchMode }> = [
  { text: "介绍下雇主责任险", mode: "quick" },
  { text: "雇主责任险和工伤保险的区别？", mode: "semantic" },
  { text: "搜索保险行业 AI 最新新闻", mode: "web" },
];

interface SessionState {
  sessions: ChatSession[];
  currentSessionId: string;
}

export default function App() {
  const [sessionState, setSessionState] = useState<SessionState>(() => loadSessionState());
  const [isProcessing, setIsProcessing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { sessions, currentSessionId } = sessionState;
  const currentSession = sessions.find((session) => session.id === currentSessionId) ?? sessions[0];
  const currentMessages = currentSession?.messages ?? [];
  const sidebarSessions = useMemo(() => visibleSessions(sessions), [sessions]);
  const displayedMessages = useMemo(() => [welcomeMessage, ...currentMessages], [currentMessages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    saveSessionState(sessions, currentSessionId);
  }, [sessions, currentSessionId]);

  useEffect(() => {
    scrollToBottom();
  }, [displayedMessages]);

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
    setSessionState((prev) => ({ ...prev, currentSessionId: sessionId }));
  };

  const handleDeleteSession = (sessionId: string) => {
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
    URL.revokeObjectURL(url);
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

  const handleSend = async (text: string, mode: SearchMode) => {
    if (!text.trim() || isProcessing || !currentSession) return;

    const sessionId = currentSession.id;
    const userMessage: Message = {
      id: createId(),
      role: "user",
      content: text,
    };
    const aiMessageId = createId();
    const aiMessage: Message = {
      id: aiMessageId,
      role: "ai",
      content: "",
      isLoading: true,
      mode,
    };

    setNotice(null);
    updateSessionMessages(sessionId, (messages) => [...messages, userMessage, aiMessage]);
    setIsProcessing(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, mode }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`请求失败：${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let content = "";
      updateSessionMessages(sessionId, (messages) =>
        messages.map((message) => (message.id === aiMessageId ? { ...message, isLoading: false, isStreaming: true } : message)),
      );

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        content += decoder.decode(value, { stream: true });
        updateSessionMessages(sessionId, (messages) =>
          messages.map((message) => (message.id === aiMessageId ? { ...message, content } : message)),
        );
      }

      content += decoder.decode();
      updateSessionMessages(sessionId, (messages) =>
        messages.map((message) =>
          message.id === aiMessageId
            ? {
                ...message,
                content: content || "没有获取到回答，请稍后重试。",
                isStreaming: false,
                sources: mode === "web" ? ["联网搜索", "本地资料库"] : ["本地资料库"],
              }
            : message,
        ),
      );
    } catch (error) {
      updateSessionMessages(sessionId, (messages) =>
        messages.map((message) =>
          message.id === aiMessageId
            ? {
                ...message,
                isLoading: false,
                isStreaming: false,
                content: error instanceof Error ? error.message : "请求失败，请检查后端服务是否已启动。",
              }
            : message,
        ),
      );
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#f8f9fb] font-sans text-slate-900">
      <Sidebar
        collapsed={sidebarCollapsed}
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
        <header className="flex h-[74px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div>
            <h1 className="text-xl font-bold leading-6 text-slate-950">保险资料智能问答系统</h1>
            <p className="mt-1 text-sm text-slate-500">面向业务人员的专业保险知识库助手</p>
          </div>
          <button
            onClick={handleNewChat}
            className="flex items-center rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            <MessageSquarePlus className="mr-2 h-4 w-4" />
            开启新对话
          </button>
        </header>

        <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-[#f6f7f9]">
          <div className="min-h-0 flex-1 overflow-y-auto px-8 py-8">
            <div className="mx-auto flex w-full max-w-[980px] flex-col gap-5">
              {notice && (
                <div className="ml-14 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm font-medium text-blue-700">
                  {notice}
                </div>
              )}

              {displayedMessages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {currentMessages.length === 0 && (
                <div className="ml-14 grid grid-cols-3 gap-4">
                  {suggestions.map((item) => (
                    <button
                      key={item.text}
                      onClick={() => handleSend(item.text, item.mode)}
                      className="h-16 rounded-xl border border-slate-200 bg-white px-4 text-left text-sm font-medium leading-5 text-slate-800 transition-colors hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                    >
                      {item.text}
                    </button>
                  ))}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {isProcessing && (
            <div className="pointer-events-none absolute bottom-[100px] left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-medium text-blue-600 shadow-sm">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
              正在检索资料，请稍候...
            </div>
          )}

          <div className="shrink-0 border-t border-slate-200 bg-white/72 px-8 py-4 backdrop-blur">
            <div className="mx-auto w-full max-w-[980px]">
              <ChatInput onSend={handleSend} isProcessing={isProcessing} />
              <p className="mt-3 text-center text-xs text-slate-500">
                AI 生成的内容仅供参考，不作为最终承保或理赔结论。
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
