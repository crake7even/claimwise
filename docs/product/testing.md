# 测试规格

每次修改后按改动类型选择级别执行；高级别包含低级别。

| 级别 | 触发条件 | 执行内容 | 通过标准 |
|---|---|---|---|
| L0 基础 | 每次改动 | `backend`: `python -m unittest discover -s tests`、`python eval/validate_dataset.py`；`frontend`: `npm run lint && npm run build` | 全部通过 |
| L1 检索 | 切分、分词、融合、Rerank、查询改写 | L0 + `eval/run_eval.py`（离线 quick）+ `eval/run_eval.py --online --mode full`（dev） | Hit@1、Recall@3000字 较上一版下降不超过 0.02 |
| L2 生成 | 提示词、生成模型、上下文拼接 | L0 + `eval/smoke.py` + `eval/run_judge.py --mode semantic`（dev） | 冒烟全部通过；忠实度不下降、误拒率不上升 |
| L3 界面 | 前端改动 | L0 + 浏览器冒烟：桌面与 375px 宽度各一遍（提问、引用展开、多轮、停止生成、模式切换、侧边栏） | 清单逐项通过 |
| L4 发布 | 合并 / 部署前后 | 对应级别 + holdout 评测；部署后 `eval/smoke.py --base-url <线上 API>` 与 `/api/health` | 线上冒烟全部通过 |

## 回归规则

每修复一个 bug，补充一个能复现它的单元测试或冒烟场景（`eval/smoke.py` 中的 `SCENARIOS`），先确认其在修复前失败、修复后通过。

## 说明

- 单元测试会 mock 模型与外部服务，只验证流程与协议；提示词和模型行为由冒烟场景与 LLM-judge 覆盖。
- 在线评测与冒烟需要 `DASHSCOPE_API_KEY`（联网场景还需要 `BOCHA_API_KEY`），会产生少量调用费用。
