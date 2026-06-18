import React from "react";
import {
  Bot,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  History,
  MessageSquare,
  MessageSquarePlus,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onFAQClick: (question: string) => void;
  onNewChat: () => void;
}

const recentQueries = ["雇主责任险对比", "工伤保险咨询"];

export function Sidebar({ collapsed, onToggle, onFAQClick, onNewChat }: SidebarProps) {
  const navItemClass =
    "flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-blue-50 hover:text-blue-700";
  const activeNavItemClass =
    "flex h-11 items-center gap-3 rounded-lg bg-blue-50 px-3 text-sm font-semibold text-blue-700 transition-colors hover:bg-blue-100";

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

      <div className="min-h-0 flex-1 overflow-hidden px-3 py-5">
        {!collapsed && <p className="mb-2 px-2 text-xs font-bold text-slate-700">会话管理</p>}
        <nav className="space-y-2">
          <button
            type="button"
            onClick={onNewChat}
            className={`${activeNavItemClass} ${collapsed ? "justify-center px-0" : ""}`}
            title="新对话"
          >
            <MessageSquarePlus className="h-4 w-4 shrink-0" />
            {!collapsed && <span>新对话</span>}
          </button>
          <button type="button" className={`${navItemClass} ${collapsed ? "justify-center px-0" : ""}`} title="历史会话">
            <History className="h-4 w-4 shrink-0" />
            {!collapsed && <span>历史会话</span>}
          </button>
          <button type="button" className={`${navItemClass} ${collapsed ? "justify-center px-0" : ""}`} title="保单分析">
            <FileSearch className="h-4 w-4 shrink-0" />
            {!collapsed && <span>保单分析</span>}
          </button>
          <button type="button" className={`${navItemClass} ${collapsed ? "justify-center px-0" : ""}`} title="理赔辅助">
            <ClipboardCheck className="h-4 w-4 shrink-0" />
            {!collapsed && <span>理赔辅助</span>}
          </button>
        </nav>

        {!collapsed && (
          <div className="mt-5">
            <p className="mb-2 px-2 text-xs font-bold text-slate-700">最近查询</p>
            <div className="space-y-1">
              {recentQueries.map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => onFAQClick(query)}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{query}</span>
                </button>
              ))}
            </div>
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
