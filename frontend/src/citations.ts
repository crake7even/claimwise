/** 回答正文中的引用标记解析：兼容 [1]、[1][2]、[1,2]、[1、2]、[1-3]、【1】，不误伤 Markdown 链接 [文字](url)。 */

export const CITATION_PREFIX = "#cite-";

// 只匹配闭合的标记：流式输出中途的半截 "[1" 不会被识别，避免闪成错误角标
const CITATION_RE = /[[【]\s*(\d{1,2}(?:\s*[,，、\-–~]\s*\d{1,2})*)\s*[\]】](?!\()/g;
const MAX_RANGE = 20;

function expandGroup(group: string): number[] {
  const ids: number[] = [];
  for (const part of group.split(/\s*[,，、]\s*/)) {
    const bounds = part.split(/\s*[-–~]\s*/).map(Number);
    if (bounds.length === 2 && bounds[0] <= bounds[1] && bounds[1] - bounds[0] < MAX_RANGE) {
      for (let id = bounds[0]; id <= bounds[1]; id += 1) ids.push(id);
    } else {
      ids.push(...bounds);
    }
  }
  return ids;
}

/** 把引用标记转成指向 #cite-n 的 Markdown 链接；不在本轮来源里的编号保持原样文本。 */
export function linkCitations(content: string, validIds: Iterable<number>): string {
  const valid = new Set(validIds);
  return content.replace(CITATION_RE, (match, group: string) => {
    const ids = expandGroup(group);
    if (!ids.some((id) => valid.has(id))) return match;
    return ids
      .map((id) => (valid.has(id) ? `[${id}](${CITATION_PREFIX}${id})` : `\\[${id}\\]`))
      .join("");
  });
}

/** 正文实际引用到的、且属于本轮来源的编号集合。 */
export function citedIds(content: string, validIds: Iterable<number>): Set<number> {
  const valid = new Set(validIds);
  const cited = new Set<number>();
  for (const match of content.matchAll(CITATION_RE)) {
    for (const id of expandGroup(match[1])) {
      if (valid.has(id)) cited.add(id);
    }
  }
  return cited;
}
