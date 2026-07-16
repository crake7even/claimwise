import React, { useRef } from "react";
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  Download,
  History,
  MessageSquare,
  MessageSquarePlus,
  Trash2,
  Upload,
} from "lucide-react";
import type { ChatSession } from "../types";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  sessions: ChatSession[];
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
  onExport: () => void;
  onImport: (file: File) => void;
}

export function Sidebar({
  collapsed,
  onToggle,
  onNewChat,
  sessions,
  currentSessionId,
  onSelectSession,
  onDeleteSession,
  onExport,
  onImport,
}: SidebarProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const primaryButtonClass =
    "flex h-11 items-center gap-3 rounded-lg bg-blue-600 px-3 text-sm font-semibold text-white shadow-sm shadow-blue-100 transition-colors hover:bg-blue-700";
  const utilityButtonClass =
    "flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950";

  return (
    <aside
      className={`flex h-full shrink-0 flex-col border-r border-slate-200 bg-white transition-[width] duration-300 ${
        collapsed ? "w-[76px]" : "w-[260px]"
      }`}
    >
      <div className={`flex h-[74px] shrink-0 items-center border-b border-slate-100 px-4 ${collapsed ? "justify-center" : "gap-3"}`}>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
          <Bot className="h-5 w-5" />
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <h2 className="truncate text-lg font-bold leading-5 text-slate-950">保险助理</h2>
            <p className="mt-1 truncate text-xs text-slate-500">智能问答系统</p>
          </div>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-3 py-5">
        {!collapsed && <p className="mb-2 px-2 text-xs font-bold text-slate-700">会话管理</p>}
        <div className="space-y-2">
          <button
            type="button"
            onClick={onNewChat}
            className={`${primaryButtonClass} ${collapsed ? "justify-center px-0" : ""}`}
            title="开启新对话"
          >
            <MessageSquarePlus className="h-4 w-4 shrink-0" />
            {!collapsed && <span>开启新对话</span>}
          </button>

          <input
            ref={fileInputRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onImport(file);
              event.target.value = "";
            }}
          />

          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className={`${utilityButtonClass} ${collapsed ? "justify-center px-0" : ""}`}
            title="导入历史"
          >
            <Upload className="h-4 w-4 shrink-0" />
            {!collapsed && <span>导入历史</span>}
          </button>

          <button
            type="button"
            onClick={onExport}
            className={`${utilityButtonClass} ${collapsed ? "justify-center px-0" : ""}`}
            title="导出历史"
          >
            <Download className="h-4 w-4 shrink-0" />
            {!collapsed && <span>导出历史</span>}
          </button>
        </div>

        {!collapsed && (
          <div className="mt-6 flex min-h-0 flex-1 flex-col">
            <div className="mb-2 flex items-center gap-2 px-2 text-xs font-bold text-slate-700">
              <History className="h-3.5 w-3.5" />
              历史会话
            </div>
            <div className="min-h-0 space-y-1 overflow-y-auto pr-1">
              {sessions.length === 0 ? (
                <div className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-xs leading-5 text-slate-500">
                  开始提问后，会话会自动保存到这里。
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group flex items-center rounded-lg transition-colors ${
                      session.id === currentSessionId
                        ? "bg-blue-50 text-blue-700"
                        : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectSession(session.id)}
                      className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2 text-left text-sm"
                      title={session.title}
                    >
                      <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                      <span className="truncate">{session.title}</span>
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteSession(session.id);
                      }}
                      className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-400 opacity-0 transition hover:bg-white hover:text-red-600 group-hover:opacity-100"
                      title="删除会话"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {collapsed && (
          <div className="mt-3 space-y-2">
            {sessions.slice(0, 6).map((session) => (
              <button
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session.id)}
                className={`flex h-10 w-full items-center justify-center rounded-lg transition-colors ${
                  session.id === currentSessionId ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-100"
                }`}
                title={session.title}
              >
                <MessageSquare className="h-4 w-4" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="shrink-0 border-t border-slate-100 p-3">
        <button
          type="button"
          onClick={onToggle}
          className={`flex h-10 w-full items-center rounded-lg text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 ${
            collapsed ? "justify-center" : "justify-between px-3"
          }`}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {!collapsed && <span>收起侧边栏</span>}
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
