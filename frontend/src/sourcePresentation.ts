import type { Source } from "./types";

// 与后端 public_source 保持一致：兼容 localStorage 和导出文件中的旧格式来源（带文件编号、检索前缀行、纯序号条款名）
const NUMBER_ONLY_SECTION = /^[\s一二三四五六七八九十百零\d、，,.．:：()（）]*$/;
const SECTION_MAX_CHARS = 30;

export function sourceTitle(source: Source): string {
  return source.kind === "local" ? source.title.replace(/^\d+-/, "") : source.title;
}

export function sourceExcerpt(source: Source): { heading: string; text: string } {
  let heading = source.section ?? "";
  if (source.kind !== "local") return { heading, text: source.snippet };
  const lines = source.snippet.split(/\r?\n/);
  const prefix = `《${sourceTitle(source)}》${heading}`.trim();
  if (lines[0]?.trim() === prefix) lines.shift();
  while (lines.length && !lines[0].trim()) lines.shift();
  const firstLine = lines[0]?.trim() ?? "";
  if (heading && firstLine === heading) {
    lines.shift();
  } else if (/^Q\s*\d+/.test(heading) && firstLine.startsWith(heading)) {
    heading = firstLine;
    lines.shift();
  } else if (NUMBER_ONLY_SECTION.test(heading) && firstLine) {
    if (Array.from(firstLine).length <= SECTION_MAX_CHARS) {
      heading = firstLine;
      lines.shift();
    } else {
      heading = `${Array.from(firstLine).slice(0, SECTION_MAX_CHARS).join("")}…`;
    }
  }
  return { heading, text: lines.join("\n").trim() };
}

export interface SourceGroup {
  key: string;
  title: string;
  kind: Source["kind"];
  url?: string;
  sources: Source[];
}

/** 同一文档（联网来源按网址）合并为一组，保持首次出现的顺序。 */
export function groupSources(sources: Source[]): SourceGroup[] {
  const groups = new Map<string, SourceGroup>();
  for (const source of sources) {
    const title = sourceTitle(source);
    const key = source.kind === "local" ? `local:${title}` : `web:${source.url || source.id}`;
    const group = groups.get(key) ?? { key, title, kind: source.kind, url: source.url, sources: [] };
    group.sources.push(source);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** 按正文是否引用拆成"引用资料"和"其他检索结果"；回答没有任何引用时 cited 为空。 */
export function splitByCitation(groups: SourceGroup[], cited: Set<number>): { cited: SourceGroup[]; others: SourceGroup[] } {
  const result = { cited: [] as SourceGroup[], others: [] as SourceGroup[] };
  for (const group of groups) {
    (group.sources.some((source) => cited.has(source.id)) ? result.cited : result.others).push(group);
  }
  return result;
}
