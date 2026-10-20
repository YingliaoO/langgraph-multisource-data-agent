# GustoBot 评估体系说明

## 1. Eval 是什么

GustoBot 的 Eval 不是普通单元测试，而是对真实 Agent 行为进行端到端考试：

```text
JSONL Case
↓
真实 HTTP Chat API
↓
Router
↓
Planner
↓
Tool Selection
↓
Tool Execution
↓
Evidence
↓
Answer
↓
Metrics
```

Eval runner 位于：

```text
eval/run_eval.py
```

典型输出：

```text
cases.jsonl
summary.json
report.md
```

## 2. Unit Test 与 Eval 的区别

### Unit Test

关注：

- 一个函数/组件是否按契约工作
- 通常可 mock LLM/DB
- 快、确定、适合代码回归

### Eval

关注：

- Router 是否选对产品 route
- Planner/Tool Selection 是否正确
- 工具是否真正执行
- status 是否符合预期
- Evidence 是否存在
- expected fact 是否得到支持
- fallback、timeout 和 latency 是否真实发生

## 3. 当前正式 Enterprise Retail dataset

```text
eval/datasets/enterprise_retail_v1.jsonl
```

共 12 个 case：

### SQL × 5

1. 订单总数 = 12
2. 品类销量聚合
3. 客户数量 = 5
4. 不存在订单 → `empty`
5. DELETE 请求 → policy rejection / `error`

### Graph × 3

6. Aurora → NorthStar Electronics
7. NorthStar → supplied products
8. Aurora → Electronics category

### RAG × 3

9. Electronics 非质量退货 = 7 days
10. NorthStar SLA = 48h
11. 退款率 > 15% → 1 business day SOP

### Control × 1

12. 普通问题 → `general-query`

File ingestion 仍放在 smoke，而不是强行放进正式 data-query grounding dataset，因为 file-query 当前契约只证明 ingestion submission acknowledgement。

## 4. 核心指标

### 4.1 HTTP

```text
http_success_rate
```

只回答 transport/API 是否成功，不代表 Agent 业务结果正确。

### 4.2 Route

```text
route_accuracy
```

比较 canonical expected route 与实际 route。

### 4.3 Tool Selection

```text
tool_selection_accuracy
```

只评价选了什么工具，不能用 dispatch 成功代替真正执行成功。

### 4.4 Tool Execution

```text
tool_execution_coverage
tool_execution_success_rate
```

必须来自真正的 tool execution terminal event / ToolResult，而不是仅看到 tool name。

### 4.5 Execution Status

```text
execution_status_accuracy
```

用于区分：

```text
success
empty
partial
error
```

### 4.6 Evidence

```text
evidence_available_accuracy
expected_fact_supported_by_evidence_rate
```

Evidence availability 和事实支持是两件事：

- 有 Evidence 不代表它一定支持 expected fact。
- answer 中出现事实也不等于 Evidence 支持。

### 4.7 Fact Coverage

```text
fact_coverage
```

当前是字符串/事实覆盖类指标，不等于严格 grounded faithfulness judge。

## 5. 分母规则

### 没有 expected facts

例如：

- `empty`
- policy rejection
- general control

不应强行进入 fact coverage 分母。

### 预期无 Evidence

policy rejection 的 `evidence=0` 是正确结果，不应降低 evidence correctness。

### null

无法计算的指标保持 `null`，不猜测数值，也不把 null 自动当失败。

## 6. Timeout latency 修正

过去只统计：

```text
start → done
```

会导致 timeout/error 没有 done event 时从平均 tool latency 消失，形成 survivor bias。

当前同时记录：

```text
completed latency
observed duration
```

例如 tool 100 秒 timeout：

```text
completed latency = null
observed_duration_ms_tool ≈ 100000
```

因此：

```text
avg_completed_latency_ms_tool
```

用于成功完成样本；

```text
avg_observed_duration_ms_tool
```

反映包含错误/超时在内的真实等待。

## 7. Enterprise Retail 第一版正式 baseline

首轮 12-case baseline：

```text
cases_total: 12
http_success_rate: 1.0000
route_accuracy: 1.0000
tool_selection_accuracy: 1.0000
tool_execution_coverage: 1.0000
execution_status_accuracy: 0.9167
evidence_available_accuracy: 0.9167
fact_coverage: 0.8333
expected_fact_supported_by_evidence_rate: 0.7778
fallback_rate: 0.1667
avg_total_latency_ms: 66398.40
p95_total_latency_ms: 155394.53
avg_observed_duration_ms_tool: 17978.73
avg_completed_latency_ms_tool: 9776.35
```

这些数字属于一次真实环境快照，不是 SLA。可公开的脱敏逐 case 摘要见 [Enterprise Retail v1 首轮报告](../eval/reports/enterprise_retail_v1_initial.md)；运行时 dataset 与当前提交版本的 12 条评测语义字段一致，但字节哈希不同。

## 8. Baseline 中真实暴露的问题

### 8.1 `enterprise_sql_customer_count`

预期：

```text
status=success
fact=5
```

实际：

```text
tool 100s timeout
status=error
evidence=0
observed_duration≈100002ms
```

这是一个真实 reliability failure，不应通过修改 expected status 掩盖。

### 8.2 两个 `router_timeout`

有两个 case 出现 Router timeout fallback，但最终 route/tool/fact 正确。

这影响：

- fallback rate
- latency

不影响最终事实 correctness。

### 8.3 RAG SOP 中英文 literal mismatch

`enterprise_rag_refund_sop` 的 answer/evidence 语义正确，包含：

```text
15%
1 个工作日
```

但 dataset expected fact 保留：

```text
"1 business day"
```

当前 literal matcher 因语言不一致只匹配一部分。因此首轮 baseline 保留这个 limitation，不通过修改 expected fact 美化历史分数。

## 9. core_v1 的当前定位

原项目中的 `core_v1` 属于：

> **Legacy Recipe regression / historical baseline**

其数据及素材的再分发权尚未核实，因此公开快照不包含该数据集；本快照的 runner 默认使用 `enterprise_retail_v1.jsonl`。

当前产品默认域应使用：

```text
enterprise_retail_v1
```

## 10. HTTP Contract Tests

旧 `tests/test_chat_api.py` 曾存在 async function 未正确执行、Recipe 手工脚本式问题。

当前已改成真正的 mock ASGI HTTP contract tests，覆盖：

- SQL execution contract
- Graph execution contract
- RAG execution contract
- SQL policy rejection

测试验证：

```text
HTTP 200
route=data-query
execution.contract_version=1
canonical tool name
status
statement language
Evidence
RAG source=pgvector
policy rejection 无 Evidence
```

## 11. 当前测试快照

当前项目 `.venv` 全量测试：

```text
183 passed
```

公开快照未纳入原项目的 legacy LightRAG、Recipe 和旧 Router 测试，故本次没有 skipped。它不等于覆盖所有历史模块，也不代替真实服务端到端验证。

## 12. Release Smoke

原仓库 Enterprise smoke 历史结果；公开快照尚需在 Docker 可用时重新验证：

```text
6/6 passed
```

覆盖：

- SQL count
- SQL category aggregation
- Graph supplier
- RAG return policy
- SQL policy rejection
- file ingestion acknowledgement

## 13. Eval 的正确使用方式

正确顺序：

```text
固定 dataset
→ 跑 baseline
→ 分析真实 failure class
→ 只修重复/高价值问题
→ 再跑相同 dataset 比较
```

不要：

```text
看到失败
→ 修改 expected facts
→ 放大 timeout
→ 重跑到出现漂亮数字
```

## 14. 当前不声称

- 不声称严格 grounded faithfulness 已完成。
- 不声称 12 case 足以代表所有企业问题。
- 不把一次环境 latency 当 SLO。
- 不把 provider long-tail 简化成数据库性能问题。
- 不把 tool selected 当 tool executed。
