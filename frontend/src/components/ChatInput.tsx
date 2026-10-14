import React, { KeyboardEvent, useEffect, useRef, useState } from "react";
import type { HealthStatus, SearchMode } from "../types";
import { ArrowUp, Globe, Sparkles, Square, Zap } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string, mode: SearchMode) => void;
  onStop: () => void;
  isProcessing: boolean;
  health: HealthStatus | null;
}

const modes: Array<{ label: string; short: string; value: SearchMode; hint: string; icon: typeof Zap; activeClass: string }> = [
  { label: "快速检索", short: "快速", value: "quick", hint: "关键词检索本地资料，响应最快", icon: Zap, activeClass: "text-amber-600" },
  { label: "语义理解", short: "语义", value: "semantic", hint: "适合口语化提问和同义表达", icon: Sparkles, activeClass: "text-violet-600" },
  { label: "联网搜索", short: "联网", value: "web", hint: "本地资料 + 联网查询实时信息", icon: Globe, activeClass: "text-sky-600" },
];

const MAX_TEXTAREA_HEIGHT = 168;

export function ChatInput({ onSend, onStop, isProcessing, health }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<SearchMode>("quick");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isAvailable = (value: SearchMode) => !health || health[value];

  useEffect(() => {
    if (!isAvailable(mode)) setMode("quick");
  }, [health]);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_TEXTAREA_HEIGHT)}px`;
  }, [text]);

  const handleSend = () => {
    if (text.trim() && !isProcessing) {
      onSend(text.trim(), mode);
      setText("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // 输入法组字（如拼音选词）时的 Enter 只用于确认候选词，不发送
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = Boolean(text.trim());

  return (
    <div className="rounded-2xl bg-white p-2 shadow-float ring-1 ring-slate-200/80 transition-shadow focus-within:ring-2 focus-within:ring-brand-300">
      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="输入保险相关问题…"
        title="Enter 发送，Shift + Enter 换行"
        className="scroll-thin block max-h-[168px] min-h-11 w-full resize-none border-none bg-transparent px-3 pt-2.5 pb-1 text-[15px] leading-7 text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0"
      />

      <div className="flex items-center justify-between gap-2 px-1 pt-1">
        <div role="radiogroup" aria-label="检索模式" className="flex items-center gap-0.5 rounded-xl bg-slate-100/80 p-0.5">
          {modes.map(({ label, short, value, hint, icon: Icon, activeClass }) => {
            const available = isAvailable(value);
            const selected = value === mode;
            return (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={selected}
                disabled={!available}
                onClick={() => setMode(value)}
                title={available ? `${label}：${hint}` : `${label}：服务端未配置，暂不可用`}
                className={`flex h-8 items-center gap-1.5 rounded-[10px] px-2.5 text-xs font-medium transition-all duration-150 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40 sm:px-3 ${
                  selected ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800"
                }`}
              >
                <Icon className={`h-3.5 w-3.5 ${selected ? activeClass : ""}`} />
                <span className="sm:hidden">{short}</span>
                <span className="hidden sm:inline">{label}</span>
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <span className="hidden text-[11px] text-slate-400 lg:inline">Enter 发送 · Shift+Enter 换行</span>
          {isProcessing ? (
            <button
              type="button"
              onClick={onStop}
              className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white transition-all hover:bg-slate-700 active:scale-95"
              title="停止生成"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={!canSend}
              className={`flex h-9 w-9 items-center justify-center rounded-xl transition-all duration-150 active:scale-95 ${
                canSend
                  ? "bg-brand-600 text-white shadow-sm shadow-brand-600/30 hover:bg-brand-700"
                  : "cursor-not-allowed bg-slate-100 text-slate-300"
              }`}
              title="发送提问"
            >
              <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2.4} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
