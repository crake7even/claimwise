import React, { useEffect, useRef, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatMessage } from "./components/ChatMessage";
import { ChatInput } from "./components/ChatInput";
import type { Message, SearchMode } from "./types";
import { Trash2 } from "lucide-react";

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

const welcomeMessage: Message = {
  id: "welcome",
  role: "ai",
  content:
    "您好！我是您的保险资料智能问答助手。您可以直接向我提问关于保险产品、保障范围、理赔流程等方面的问题。默认会优先从本地资料库中为您检索准确的信息。\n\n请问今天有什么我可以帮您的？",
};

export default function App() {
  const [messages, setMessages] = useState<Message[]>([welcomeMessage]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const updateMessage = (id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((msg) => (msg.id === id ? { ...msg, ...patch } : msg)));
  };

  const handleSend = async (text: string, mode: SearchMode) => {
    if (!text.trim() || isProcessing) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    const aiMessageId = crypto.randomUUID();
    const aiMessage: Message = {
      id: aiMessageId,
      role: "ai",
      content: "",
      isLoading: true,
      mode,
    };

    setMessages((prev) => [...prev, userMessage, aiMessage]);
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
      updateMessage(aiMessageId, { isLoading: false, isStreaming: true });

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        content += decoder.decode(value, { stream: true });
        updateMessage(aiMessageId, { content });
      }

      content += decoder.decode();
      updateMessage(aiMessageId, {
        content: content || "没有获取到回答，请稍后重试。",
        isStreaming: false,
        sources: mode === "web" ? ["联网搜索", "本地资料库"] : ["本地资料库"],
      });
    } catch (error) {
      updateMessage(aiMessageId, {
        isLoading: false,
        isStreaming: false,
        content: error instanceof Error ? error.message : "请求失败，请检查后端服务是否已启动。",
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleClear = () => {
    setMessages([
      {
        ...welcomeMessage,
        id: "welcome-clear",
        content: "对话已清空。您可以开始新的提问。",
      },
    ]);
  };

  const suggestions: Array<{ text: string; mode: SearchMode }> = [
    { text: "介绍下雇主责任险", mode: "quick" },
    { text: "雇主责任险和工伤保险的区别？", mode: "semantic" },
    { text: "搜索保险行业 AI 最新新闻", mode: "web" },
  ];

  return (
    <div className="flex h-screen w-full overflow-hidden bg-[#f8f9fb] font-sans text-slate-900">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((value) => !value)}
        onFAQClick={(text) => handleSend(text, "quick")}
        onNewChat={handleClear}
      />

      <main className="flex min-w-0 flex-1 flex-col transition-all duration-300">
        <header className="flex h-[74px] shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
          <div>
            <h1 className="text-xl font-bold leading-6 text-slate-950">保险资料智能问答系统</h1>
            <p className="mt-1 text-sm text-slate-500">面向业务人员的专业保险知识库助手</p>
          </div>
          <button
            onClick={handleClear}
            className="flex items-center rounded-lg px-3 py-2 text-sm font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900"
          >
            <Trash2 className="mr-2 h-4 w-4" />
            清空对话记录
          </button>
        </header>

        <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden bg-[#f6f7f9]">
          <div className="min-h-0 flex-1 overflow-y-auto px-8 py-8">
            <div className="mx-auto flex w-full max-w-[980px] flex-col gap-5">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {messages.length === 1 && (
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
