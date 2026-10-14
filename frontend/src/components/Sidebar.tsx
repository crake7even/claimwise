import React, { useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  History,
  MessageSquare,
  MessageSquarePlus,
  Trash2,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import type { ChatSession } from "../types";

interface SidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
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
  collapsed: desktopCollapsed,
  mobileOpen,
  onCloseMobile,
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
  // 移动端以抽屉形式完整展开，桌面端才使用折叠态
  const collapsed = desktopCollapsed && !mobileOpen;
  const primaryButtonClass =
    "flex h-10 w-full items-center gap-2.5 rounded-xl bg-brand-600 px-3 text-sm font-medium text-white shadow-sm shadow-brand-600/25 transition-all hover:bg-brand-700 active:scale-[0.98]";
  const utilityButtonClass =
    "flex h-9 flex-1 items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800";

  return (
    <>
    {mobileOpen && <div className="fixed inset-0 z-30 animate-fade bg-slate-900/40 backdrop-blur-[2px] md:hidden" onClick={onCloseMobile} />}
    <aside
      className={`fixed inset-y-0 left-0 z-40 flex h-full shrink-0 flex-col border-r border-slate-200/70 bg-white/95 backdrop-blur transition-[width,transform] duration-300 ease-out md:static md:z-auto md:translate-x-0 ${
        mobileOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
      } ${collapsed ? "w-[72px]" : "w-[264px]"}`}
    >
      <div className={`flex h-16 shrink-0 items-center px-4 ${collapsed ? "justify-center" : "gap-2.5"}`}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-sm shadow-brand-500/30">
          <ShieldCheck className="h-[18px] w-[18px]" />
        </div>
        {!collapsed && (
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-[15px] font-semibold leading-5 text-slate-900">ClaimWise</h2>
            <p className="truncate text-xs text-slate-500">保险知识库助手</p>
          </div>
        )}
        {mobileOpen && (
          <button type="button" onClick={onCloseMobile} className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 md:hidden" title="关闭">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-3 pt-2 pb-4">
        <div className={collapsed ? "space-y-2" : "space-y-1.5"}>
          <button
            type="button"
            onClick={onNewChat}
            className={`${primaryButtonClass} ${collapsed ? "justify-center px-0" : ""}`}
            title="开启新对话"
          >
            <MessageSquarePlus className="h-4 w-4 shrink-0" />
            {!collapsed && <span>新对话</span>}
          </button>
          <div className={collapsed ? "space-y-2" : "flex gap-1"}>

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
            className={`${utilityButtonClass} ${collapsed ? "h-10 w-full px-0" : ""}`}
            title="导入历史"
          >
            <Upload className="h-4 w-4 shrink-0" />
            {!collapsed && <span>导入</span>}
          </button>

          <button
            type="button"
            onClick={onExport}
            className={`${utilityButtonClass} ${collapsed ? "h-10 w-full px-0" : ""}`}
            title="导出历史"
          >
            <Download className="h-4 w-4 shrink-0" />
            {!collapsed && <span>导出</span>}
          </button>
          </div>
        </div>

        {!collapsed && (
          <div className="mt-5 flex min-h-0 flex-1 flex-col">
            <div className="mb-1.5 flex items-center gap-1.5 px-2 text-[11px] font-medium tracking-wide text-slate-400">
              <History className="h-3 w-3" />
              历史会话
            </div>
            <div className="scroll-thin min-h-0 space-y-0.5 overflow-y-auto">
              {sessions.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 px-3 py-4 text-xs leading-5 text-slate-400">
                  开始提问后，会话会自动保存到这里。
                </div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    className={`group relative flex items-center rounded-lg transition-colors ${
                      session.id === currentSessionId
                        ? "bg-brand-50 text-brand-800 before:absolute before:inset-y-2 before:left-0 before:w-[3px] before:rounded-full before:bg-brand-600"
                        : "text-slate-600 hover:bg-slate-100/70 hover:text-slate-900"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectSession(session.id)}
                      className="flex min-w-0 flex-1 items-center gap-2.5 px-3 py-2 text-left text-[13px]"
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
                      className="mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-slate-400 opacity-100 transition hover:bg-white hover:text-red-600 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100"
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
                  session.id === currentSessionId ? "bg-brand-50 text-brand-700" : "text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                }`}
                title={session.title}
              >
                <MessageSquare className="h-4 w-4" />
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="hidden shrink-0 border-t border-slate-100 p-2 md:block">
        <button
          type="button"
          onClick={onToggle}
          className={`flex h-9 w-full items-center rounded-lg text-xs font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 ${
            collapsed ? "justify-center" : "justify-between px-3"
          }`}
          title={collapsed ? "展开侧边栏" : "收起侧边栏"}
        >
          {!collapsed && <span>收起侧边栏</span>}
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
    </>
  );
}
