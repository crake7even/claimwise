import { describe, expect, it } from "vitest";
import type { Source } from "./types";
import { groupSources, sourceExcerpt, sourceTitle, splitByCitation } from "./sourcePresentation";

const local = (id: number, title: string, section: string, snippet: string): Source => ({ id, kind: "local", title, section, snippet });

describe("groupSources / splitByCitation", () => {
  const sources: Source[] = [
    local(1, "平安企业团体综合意外险", "释义", "a"),
    local(2, "雇主责任险", "Q4", "b"),
    local(3, "雇主责任险", "Q5", "c"),
    local(4, "3-平安企业团体综合意外险", "三、", "d"), // 旧格式标题也归入同一组
    local(5, "施工保", "Q1", "e"),
    { id: 6, kind: "web", title: "新闻", url: "https://example.com/a", snippet: "f" },
  ];

  it("同一文档合并为一组，保持出现顺序", () => {
    const groups = groupSources(sources);
    expect(groups.map((g) => [g.title, g.sources.map((s) => s.id)])).toEqual([
      ["平安企业团体综合意外险", [1, 4]],
      ["雇主责任险", [2, 3]],
      ["施工保", [5]],
      ["新闻", [6]],
    ]);
  });

  it("按被引用编号拆分引用资料与其他检索结果", () => {
    const split = splitByCitation(groupSources(sources), new Set([1, 2, 4]));
    expect(split.cited.map((g) => g.title)).toEqual(["平安企业团体综合意外险", "雇主责任险"]);
    expect(split.others.map((g) => g.title)).toEqual(["施工保", "新闻"]);
  });

  it("没有引用时全部归入其他", () => {
    const split = splitByCitation(groupSources(sources), new Set());
    expect(split.cited).toEqual([]);
    expect(split.others).toHaveLength(4);
  });
});

describe("旧格式来源与新格式显示一致", () => {
  it("清洗编号前缀、前缀行和纯序号条款名", () => {
    const legacy = local(1, "3-平安企业团体综合意外险", "三、", "《平安企业团体综合意外险》三、\n三、责任免除\n酒后驾驶不赔");
    const current = local(1, "平安企业团体综合意外险", "三、责任免除", "酒后驾驶不赔");
    expect(sourceTitle(legacy)).toBe(sourceTitle(current));
    expect(sourceExcerpt(legacy)).toEqual(sourceExcerpt(current));
    expect(sourceExcerpt(current)).toEqual({ heading: "三、责任免除", text: "酒后驾驶不赔" });
  });

  it("问答类旧数据补全问句", () => {
    const question = "Q3：员工在上下班途中发生交通事故，雇主责任险是否赔偿？";
    const legacy = local(1, "2-雇主责任险", question.slice(0, 24), `《雇主责任险》${question.slice(0, 24)}\n${question}\nA：赔偿。`);
    const current = local(1, "雇主责任险", question, "A：赔偿。");
    expect(sourceExcerpt(legacy)).toEqual(sourceExcerpt(current));
  });

  it("超长首行截断为条款名，正文保留", () => {
    const line = "三、" + "被保险人酒后驾驶机动车".repeat(5);
    const legacy = local(1, "3-意外险", "三、", `《意外险》三、\n${line}`);
    expect(sourceExcerpt(legacy)).toEqual({ heading: `${line.slice(0, 30)}…`, text: line });
  });

  it("联网来源原样展示", () => {
    const web: Source = { id: 2, kind: "web", title: "1-新闻", url: "https://example.com", snippet: "a\nb" };
    expect(sourceTitle(web)).toBe("1-新闻");
    expect(sourceExcerpt(web)).toEqual({ heading: "", text: "a\nb" });
  });
});
