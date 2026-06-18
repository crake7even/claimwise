import React, { KeyboardEvent, useState } from "react";
import type { SearchMode } from "../types";
import { Select } from "@base-ui-components/react/select";
import { SendHorizontal, Zap } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string, mode: SearchMode) => void;
  isProcessing: boolean;
}

const modes: Array<{ label: string; value: SearchMode; hint: string }> = [
  { label: "快速检索", value: "quick", hint: "本地资料优先，响应最快" },
  { label: "语义理解", value: "semantic", hint: "适合模糊提问和同义表达" },
  { label: "联网搜索", value: "web", hint: "查询实时信息或库外资料" },
];

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

export function ChatInput({ onSend, isProcessing }: ChatInputProps) {
  const [text, setText] = useState("");
  const [mode, setMode] = useState<SearchMode>("quick");

  const handleSend = () => {
    if (text.trim() && !isProcessing) {
      onSend(text.trim(), mode);
      setText("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  };

  const activeMode = modes.find((item) => item.value === mode) ?? modes[0];

  return (
    <div className="flex h-16 items-center gap-3 rounded-2xl border border-slate-200 bg-white p-2 shadow-lg shadow-slate-200/70 transition-all focus-within:border-blue-200 focus-within:ring-4 focus-within:ring-blue-100/70">
      <Select.Root value={mode} onValueChange={(val) => val && setMode(val as SearchMode)}>
        <Select.Trigger className="flex h-11 w-[132px] shrink-0 select-none items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-500 active:bg-white data-[popup-open]:bg-white">
          <span className="flex min-w-0 items-center gap-2">
            <Zap className="h-4 w-4 shrink-0 text-amber-500" />
            <span className="truncate">{activeMode.label}</span>
          </span>
          <Select.Icon className="flex text-slate-500">
            <ChevronUpDownIcon />
          </Select.Icon>
        </Select.Trigger>
        <Select.Portal>
          <Select.Positioner className="z-50 outline-none" sideOffset={8}>
            <Select.Popup className="max-h-[var(--available-height)] origin-[var(--transform-origin)] overflow-y-auto rounded-xl border border-slate-100 bg-white p-1 text-slate-700 shadow-xl shadow-slate-200/50 outline outline-1 outline-slate-200 transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[ending-style]:opacity-0 data-[ending-style]:transition-none data-[starting-style]:scale-95 data-[starting-style]:opacity-0">
              {modes.map(({ label, value, hint }) => (
                <Select.Item
                  key={value}
                  value={value}
                  className="grid min-w-[210px] cursor-pointer grid-cols-[0.9rem_1fr] items-center gap-2 rounded-lg py-2.5 pr-4 pl-2.5 text-sm leading-4 outline-none select-none data-[highlighted]:bg-slate-100 data-[highlighted]:text-slate-900"
                >
                  <Select.ItemIndicator className="col-start-1">
                    <CheckIcon className="size-3 text-blue-600" />
                  </Select.ItemIndicator>
                  <div className="col-start-2">
                    <Select.ItemText className="font-semibold">{label}</Select.ItemText>
                    <div className="mt-1 text-xs text-slate-400">{hint}</div>
                  </div>
                </Select.Item>
              ))}
            </Select.Popup>
          </Select.Positioner>
        </Select.Portal>
      </Select.Root>

      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="请输入您的保险相关问题..."
        className="min-w-0 flex-1 border-none bg-transparent px-2 py-2 text-base text-slate-900 outline-none placeholder:text-slate-400 focus:ring-0"
      />

      <button
        onClick={handleSend}
        disabled={!text.trim() || isProcessing}
        className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-all ${
          text.trim() && !isProcessing
            ? "bg-blue-600 text-white shadow-md shadow-blue-200 hover:bg-blue-700"
            : "cursor-not-allowed bg-slate-200 text-slate-400"
        }`}
        title="发送提问"
      >
        <SendHorizontal className="h-5 w-5" />
      </button>
    </div>
  );
}
