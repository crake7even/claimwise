import React, { KeyboardEvent, useEffect, useRef, useState } from "react";
import type { HealthStatus, SearchMode } from "../types";
import { Select } from "@base-ui/react/select";
import { Globe, SendHorizontal, Sparkles, Square, Zap } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string, mode: SearchMode) => void;
  onStop: () => void;
  isProcessing: boolean;
  health: HealthStatus | null;
}

const modes: Array<{ label: string; value: SearchMode; hint: string; icon: typeof Zap; iconClass: string }> = [
  { label: "快速检索", value: "quick", hint: "关键词检索本地资料，响应最快", icon: Zap, iconClass: "text-amber-500" },
  { label: "语义理解", value: "semantic", hint: "适合口语化提问和同义表达", icon: Sparkles, iconClass: "text-violet-500" },
  { label: "联网搜索", value: "web", hint: "本地资料 + 联网查询实时信息", icon: Globe, iconClass: "text-sky-500" },
];

const MAX_TEXTAREA_HEIGHT = 160;

function ChevronUpDownIcon(props: React.ComponentProps<"svg">) {
  return (
    <svg width="8" height="12" viewBox="0 0 8 12" fill="none" stroke="currentColor" strokeWidth="1.5" {...props}>
      <path d="M0.5 4.5L4 1.5L7.5 4.5" />
      <path d="M0.5 7.5L4 10.5L7.5 7.5" />
    </svg>
  );
}

function CheckIcon(props: React.ComponentProps<"svg">) {
  return (
    <svg fill="currentColor" width="10" height="10" viewBox="0 0 10 10" {...props}>
      <path d="M9.1603 1.12218C9.50684 1.34873 9.60427 1.81354 9.37792 2.16038L5.13603 8.66012C5.01614 8.8438 4.82192 8.96576 4.60451 8.99384C4.3871 9.02194 4.1683 8.95335 4.00574 8.80615L1.24664 6.30769C0.939709 6.02975 0.916013 5.55541 1.19372 5.24822C1.47142 4.94102 1.94536 4.91731 2.2523 5.19524L4.36085 7.10461L8.12299 1.33999C8.34934 0.993152 8.81376 0.895638 9.1603 1.12218Z" />
    </svg>
  );
}

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

  const activeMode = modes.find((item) => item.value === mode) ?? modes[0];
  const ActiveIcon = activeMode.icon;

  return (
    <div className="flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/70 transition-all focus-within:border-blue-200 focus-within:ring-4 focus-within:ring-blue-100/70 sm:gap-3">
      <Select.Root value={mode} onValueChange={(val) => val && setMode(val as SearchMode)}>
        <Select.Trigger
          className="flex h-11 w-11 shrink-0 select-none items-center justify-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-0 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 active:bg-white data-[popup-open]:bg-white sm:w-[132px] sm:justify-between sm:px-3"
          title={`检索模式：${activeMode.label}`}
        >
          <span className="flex min-w-0 items-center gap-2">
            <ActiveIcon className={`h-4 w-4 shrink-0 ${activeMode.iconClass}`} />
            <span className="hidden truncate sm:inline">{activeMode.label}</span>
          </span>
          <Select.Icon className="hidden text-slate-500 sm:flex">
            <ChevronUpDownIcon />
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Positioner className="z-50 outline-none" sideOffset={8}>
            <Select.Popup className="max-h-[var(--available-height)] origin-[var(--transform-origin)] overflow-y-auto rounded-xl border border-slate-100 bg-white p-1 text-slate-700 shadow-xl shadow-slate-200/50 outline outline-1 outline-slate-200 transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:transition-none data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
              {modes.map(({ label, value, hint, icon: Icon, iconClass }) => {
                const available = isAvailable(value);
                return (
                  <Select.Item
                    key={value}
                    value={value}
                    disabled={!available}
                    className="grid min-w-[230px] cursor-pointer grid-cols-[0.9rem_1rem_1fr] items-center gap-2 rounded-lg py-2.5 pr-4 pl-2.5 text-sm leading-4 outline-none select-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[highlighted]:bg-slate-100 data-[highlighted]:text-slate-900"
                  >
                    <Select.ItemIndicator className="col-start-1">
                      <CheckIcon className="size-3 text-blue-600" />
                    </Select.ItemIndicator>
                    <Icon className={`col-start-2 h-4 w-4 ${iconClass}`} />
                    <div className="col-start-3">
                      <Select.ItemText className="font-semibold">{label}</Select.ItemText>
                      <div className="mt-1 text-xs text-slate-400">{available ? hint : "服务端未配置，暂不可用"}</div>
                    </div>
                  </Select.Item>
                );
              })}
            </Select.Popup>
          </Select.Positioner>
        </Select.Portal>
      </Select.Root>

      <textarea
        ref={textareaRef}
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="请输入保险相关问题"
        title="Enter 发送，Shift + Enter 换行"
        className="min-h-11 min-w-0 flex-1 resize-none border-none bg-transparent px-1 py-2.5 text-base leading-6 text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0 sm:px-2"
      />

      {isProcessing ? (
        <button
          type="button"
          onClick={onStop}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-white transition-colors hover:bg-slate-900"
          title="停止生成"
        >
          <Square className="h-4 w-4 fill-current" />
        </button>
      ) : (
        <button
          type="button"
          onClick={handleSend}
          disabled={!text.trim()}
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all ${
            text.trim()
              ? "bg-blue-600 text-white shadow-md shadow-blue-200 hover:bg-blue-700"
              : "cursor-not-allowed bg-slate-200 text-slate-400"
          }`}
          title="发送提问"
        >
          <SendHorizontal className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
