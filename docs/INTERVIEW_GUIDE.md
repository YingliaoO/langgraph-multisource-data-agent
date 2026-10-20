# GustoBot 面试说明与高频追问

## 1. 30 秒项目介绍

> GustoBot 是一个基于 LangGraph 的多源企业 Data Agent。我把 MySQL、PGVector 企业知识库和 Neo4j 图数据统一成三个 canonical tools：`sql_agent`、`knowledge_rag` 和 `graph_tool`。用户问题先经过 Semantic Router 和 Generic Planner，再由 Tool Selection 选择数据工具；工具结果统一成 ToolResult 和 Evidence，最终由共享 AnswerGenerator 生成答案，并通过 versioned Execution Contract 暴露 SQL/Cypher、证据、耗时和 fallback。项目还做了 SQL 只读安全、bounded repair、RAG domain isolation、正式 Enterprise Eval 和 HTTP contract tests。

## 2. 1-2 分钟项目介绍

可以按“问题 → 架构 → 工程难点 → 验证”讲：

### 问题

企业问答往往同时包含：

- 结构化数据库统计
- 企业制度/知识文档
- 实体关系和图数据

如果给每种数据源写独立 chatbot，路由、状态、结果格式、前端展示和评估都会分裂。

### 架构

因此我把产品顶层收敛为四个 route，其中所有数据问题统一进 `data-query`；Planner 拆成 task，再从三个 canonical tools 里选择工具。工具层统一返回 ToolResult/Evidence，最终 AnswerGenerator 做 Evidence Fusion。

### 重点难点

1. SQL 安全：SQLGlot AST、只读、schema safety、LIMIT、timeout、最多一次 repair。
2. 统一证据：SQL row、RAG document、Graph record 统一成 Evidence。
3. RAG 数据正确性：用 `(domain,dataset_id,source_id)` 做稳定 identity 和 domain filter，解决跨域召回和 UUID 上传导致的重复数据。
4. 可靠性：区分 timeout、retry、fallback、partial，不通过无限重试掩盖问题。
5. Eval：正式 Enterprise Retail 12-case baseline，区分 route/tool/execution/evidence/fact。

### 验证

原仓库的 Enterprise smoke 曾达到 6/6；本公开快照的 Python 测试为 183 passed。Docker 不可用时不得声称公开快照已重新完成 smoke。历史 Eval 保留真实 timeout 和 evaluator language mismatch，不为跑分修改预期事实。

## 3. Router 和 Planner 有什么区别？

Router 是产品级分类：

```text
general / additional / data / file
```

Planner 只在 `data-query` 内拆分任务。

例如：

> “分析 Aurora 销量、供应商和退货政策。”

Router：

```text
data-query
```

Planner：

```text
task_1 销量
task_2 供应商
task_3 退货政策
```

Tool Selection：

```text
task_1 → sql_agent
task_2 → graph_tool
task_3 → knowledge_rag
```

## 4. 为什么不让 Planner 直接生成 SQL/Cypher？

因为 Planner 应负责“做什么”，Tool 负责“怎么访问具体数据源”。

如果 Planner 直接生成 SQL：

- schema 细节泄漏到 Planner
- SQL safety 无法形成独立工具边界
- 未来 Graph/RAG 难统一
- Planner prompt 更复杂

当前封装允许 `sql_agent` 内部独立做 schema retrieval 和 safety。

## 5. 为什么只有三个 canonical tools？

因为 canonical tool 应代表稳定的数据能力，而不是每一个内部实现策略。

例如：

```text
predefined Cypher
dynamic Text2Cypher
```

都是 `graph_tool` 内部策略；不应该暴露成两个 Tool 给 Planner，否则工具空间会持续膨胀。

## 6. ToolResult 和 Evidence 为什么分开？

ToolResult 回答：

> 工具执行发生了什么？

Evidence 回答：

> 哪些事实可以支撑最终回答？

例如 RAG 可检索 10 个 candidate，但最终只用 2 个 Evidence。两者不能混为一谈。

## 7. 为什么 citation_id 不是 source_id？

`source_id` 表示底层数据来源身份；同一个 source 可以在不同请求中被多次使用。

`evidence_id` 表示本次请求中某个 task 的证据实例。

因此 citation 应引用 `evidence_id`，保证本次执行可追踪。

## 8. 为什么不把 LangGraph State 直接返回前端？

内部 State 可能包含：

- debug 信息
- prompt
- 大量 rows/documents
- credentials 周边信息
- legacy fields

如果前端直接依赖 State，内部重构会破坏公共 API，也容易泄漏数据。因此引入显式 `ExecutionDTO v1` allowlist。

## 9. Partial success 怎么定义？

例如多工具：

```text
SQL success
Graph success
RAG error
```

整体：

```text
partial
```

如果：

```text
success + empty
```

整体仍是 `success`；如果只有 empty，则 `empty`。

## 10. Retry 哪些错误？

只重试明确 transient failure：

- 429（非 billing/quota）
- 502
- 503
- network/transport

不重试：

- policy rejection
- validation
- auth
- billing
- timeout
- deterministic tool error

这样避免 stacked retries 放大 latency。

## 11. 为什么 timeout 不直接 retry？

timeout 的根因未必是瞬时错误，直接 retry 可能把 100 秒变成 200 秒甚至更长。

当前先记录 timeout 和 observed duration，通过 Eval 看是否稳定重复，再决定是否修 provider/client 行为。

## 12. Text2SQL 相比普通 Demo 有什么不同？

普通 Demo 常见：

```text
Question → LLM → SQL → DB → Answer
```

当前：

```text
Question
→ Schema Retrieval
→ Analysis
→ SQL Generation
→ SQLGlot
→ Read-only
→ Table/Column Validation
→ Ambiguity Validation
→ LIMIT
→ Timeout
→ Bounded Repair
→ Revalidate
→ Execute
→ ToolResult/Evidence
→ Shared AnswerGenerator
```

重点是“把 LLM SQL 当候选，不当可信指令”。

## 13. RAG 为什么选 PGVector？

因为当前项目已经有 PostgreSQL 数据平面，可以用同一服务承载 metadata + vector，同时减少 Milvus/LightRAG 多套并行路径带来的部署和解释成本。

选择 PGVector 是产品收敛，不是声称它在所有场景都优于其他向量库。

## 14. RAG domain isolation 为什么要做？

原来唯一键近似依赖 `(source_table,source_id)`，而上传文件名包含 UUID；同一个 CSV 重传可能变成新 source_table。同时 Recipe 与 Retail 共用 corpus，没有显式 domain filter。

当前改为：

```text
(domain,dataset_id,source_id)
```

并把 Enterprise query 固定在 `domain=enterprise_retail`。这解决的是数据 correctness，不是性能优化。

## 15. 为什么 migration 放到 startup？

如果 search path 每次执行 `ALTER TABLE / backfill / cleanup / CREATE INDEX`：

- retrieval 不再是只读
- 会有 DDL lock
- 首个请求 latency 高
- 数据迁移失败和业务查询失败混在一起

所以重型迁移移动到 `kb_ingest` startup；search 只做 retrieval。

## 16. Eval 是什么？

Eval 是 Agent 的自动化考试，不等于 unit test。

它用固定 JSONL 问题真实调用 Chat API，比较：

- route
- tool
- execution status
- evidence
- facts
- fallback
- latency

## 17. 为什么 baseline 不追求 100%？

因为 baseline 的价值是暴露真实失败。

首轮 Enterprise baseline 留下：

- 一个 SQL tool timeout
- 两个 Router timeout fallback
- 一个中英文 literal matching limitation

如果为了满分去改 expected facts 或放大 timeout，就失去评测意义。

## 18. 当前最大限制是什么？

可以回答：

> 当前最大的系统性限制是外部 LLM structured-output 的 long-tail 和缺少完整依赖式多跳 scheduler。项目选择先固定 timeout、fallback、observed duration 和 Eval，而不是引入无限 retry 或复杂调度器。

## 19. 为什么不继续加 Redis/Kafka/K8s？

因为求职项目的核心价值已经从“有没有某个技术名词”转向：

- 是否有清晰工具边界
- 是否有数据契约
- 是否安全
- 是否可评估
- 是否能解释 failure

没有真实规模需求时继续堆基础设施会增加面试风险。

## 20. 推荐简历 bullet

可以写：

> 基于 LangGraph 构建多源 Enterprise Data Agent，将 MySQL Text2SQL、PGVector RAG 与 Neo4j Graph Query 收敛为 3 个 canonical tools，通过 Router/Planner 统一编排，并设计 ToolResult/Evidence/Execution Contract 实现可追踪回答与前端展示。

> 为 Text2SQL 增加 SQLGlot 语义校验、只读/Schema safety、结果上限、执行超时与 bounded repair；将模型生成 SQL 从“直接执行指令”降级为“需通过确定性安全链的候选语句”。

> 建立 Synthetic Enterprise Retail 12-case Eval baseline，分离 route/tool/execution/evidence/fact/latency 指标；修复 timeout latency survivor bias，并保留真实 provider long-tail 作为 reliability baseline。

> 为 PGVector 知识库引入 `(domain,dataset_id,source_id)` 稳定 identity、domain retrieval filter 与增量 upsert，解决跨业务域误召回和 UUID 上传导致的重复文档。

## 21. 面试表达禁区

不要说：

- “这是多个自治 Agent 协作系统。”
- “已经生产级高可用。”
- “所有回答严格 faithfulness 100%。”
- “文件上传成功就一定已经完成索引。”
- “没有任何 legacy code。”
- “所有查询都很快。”

更好的表达是明确范围、设计理由和当前限制。
