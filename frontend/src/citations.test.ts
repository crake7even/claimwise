import { describe, expect, it } from "vitest";
import { citedIds, linkCitations } from "./citations";

const ids = [1, 2, 3, 4, 5];

describe("linkCitations", () => {
  it.each([
    ["不赔[1]。", "不赔[1](#cite-1)。"],
    ["不赔[1][2]。", "不赔[1](#cite-1)[2](#cite-2)。"],
    ["见[1、2]", "见[1](#cite-1)[2](#cite-2)"],
    ["见[1,2]", "见[1](#cite-1)[2](#cite-2)"],
    ["见[1，3]", "见[1](#cite-1)[3](#cite-3)"],
    ["见[1-3]", "见[1](#cite-1)[2](#cite-2)[3](#cite-3)"],
    ["见【4】", "见[4](#cite-4)"],
    ["见[ 2 ]", "见[2](#cite-2)"],
  ])("把 %s 渲染为角标链接", (input, expected) => {
    expect(linkCitations(input, ids)).toBe(expected);
  });

  it("越界编号保持原样、不可点击", () => {
    expect(linkCitations("见[9]", ids)).toBe("见[9]");
    expect(linkCitations("见[2、9]", ids)).toBe("见[2](#cite-2)\\[9\\]");
  });

  it("不误伤 Markdown 链接和普通方括号", () => {
    expect(linkCitations("参见[条款原文](https://example.com)", ids)).toBe("参见[条款原文](https://example.com)");
    expect(linkCitations("[1](https://example.com)", ids)).toBe("[1](https://example.com)");
    expect(linkCitations("[注意]", ids)).toBe("[注意]");
  });

  it("流式中途的半截标记不变成角标", () => {
    expect(linkCitations("不赔[1", ids)).toBe("不赔[1");
    expect(linkCitations("不赔[1、", ids)).toBe("不赔[1、");
  });

  it("无来源时不改动正文", () => {
    expect(linkCitations("不赔[1]", [])).toBe("不赔[1]");
  });
});

describe("citedIds", () => {
  it("汇总各种写法的被引用编号并过滤越界", () => {
    expect([...citedIds("a[1] b[2-3] c【5】 d[9] e[x](u)", ids)].sort()).toEqual([1, 2, 3, 5]);
  });

  it("随流式内容增长更新，半截标记不计入", () => {
    expect([...citedIds("不赔[1", ids)]).toEqual([]);
    expect([...citedIds("不赔[1]", ids)]).toEqual([1]);
  });

  it("同一内容重复计算结果一致（重新打开历史会话）", () => {
    const content = "结论[2][4]，另见[1、2]";
    expect([...citedIds(content, ids)]).toEqual([...citedIds(content, ids)]);
  });
});
