# Multi-Source Data Agent 产品范围说明

## 1. 文档目的

本文冻结 Multi-Source Data Agent 当前正式产品边界，避免历史代码、兼容接口和实验能力重新进入主架构叙事。后续 README、Demo、Eval、UI、简历和面试介绍均应以本文为准。

## 2. 当前产品定义

Multi-Source Data Agent 当前定义为：

> **基于 LangGraph 的多源企业数据智能 Agent（Enterprise Data Agent）**

当前默认业务域是 **Synthetic Enterprise Retail**。公开快照不分发历史 Recipe 数据；所有 Enterprise Retail 演示数据均为合成数据。

项目的核心目标不是覆盖尽可能多的 AI 能力，而是把企业数据问答中的三类典型数据源统一起来：

- MySQL 结构化业务数据
- PostgreSQL/PGVector 企业知识文档
- Neo4j 实体关系数据

## 3. 正式产品路由

### `general-query`

适用于无需访问企业数据的普通回答，例如：

- “你好，你能做什么？”
- “解释一下这个系统的能力。”

该路径不应为了“显示 Agent 能力”而强行调用数据工具。

### `additional-query`

适用于信息不足、必须追问后才能可靠执行的数据问题，例如：

> “帮我分析这个产品最近表现。”

系统需要补充产品、时间范围或指标定义，而不是自行猜测。

### `data-query`

所有正式数据问答统一进入 `data-query`，再由 Planner 拆任务、Tool Selection 选择数据工具。

### `file-query`

用于 CSV/XLS/XLSX 数据集上传和摄取。当前 success 语义是“已提交导入任务”，不是“后台处理一定完成并可立即查询”。

## 4. 三个 canonical tools

### `sql_agent`

用途：结构化统计、聚合、明细、排序、筛选、关联查询。

主要能力：

- MySQL schema retrieval
- Text2SQL
- SQLGlot AST/语义校验
- 只读策略
- 表和字段校验
- 歧义检查
- LIMIT cap
- SQL execution timeout
- 最多一次受控 repair

### `knowledge_rag`

用途：企业制度、政策、SOP、说明文档等非结构化知识。

当前唯一默认 RAG 主链：

```text
knowledge_rag
→ kb_ingest
→ PGVector
→ Reranker
→ Evidence
```

### `graph_tool`

用途：实体关系、供应链关系、产品-品类关系、产品-活动关系等图结构问题。

内部可使用 predefined Cypher 或 dynamic Text2Cypher，但对 Agent 仍只暴露一个 `graph_tool`。

## 5. 数据与服务边界

### 默认数据后端

- MySQL
- PostgreSQL / PGVector
- Neo4j

### 默认 Docker 服务

```text
backend
mysql
neo4j
kb_postgres
kb_ingest
```

### 当前不作为默认主路径宣传

- Milvus
- Redis runtime dependency
- LightRAG
- Vision
- Image Generation
- External Search
- 通用爬虫问答
- 新的第四个 canonical tool
- 无限 ReAct
- EXPLAIN-based SQL cost optimizer
- semantic DSL / semantic layer
- query memory

这些能力可能仍在仓库中保留 legacy 代码、历史测试或参考实现，但不能出现在默认架构首屏。

## 6. 正式数据契约

当前 Agent 输出以以下契约为主：

```text
Task
→ ToolResult
→ Evidence
→ EvidenceContext
→ AnswerGenerator
→ Execution DTO
```

### ToolResult

表示“工具实际执行发生了什么”。

单工具 status：

```text
success
empty
error
```

### Evidence

表示“哪些结构化事实可以支撑最终回答”。

```text
sql_agent      → sql_row      / mysql
knowledge_rag  → document     / pgvector
graph_tool     → graph_record / neo4j
```

### Execution DTO

请求级状态：

```text
success
empty
partial
error
```

`partial` 只用于真正的部分成功，例如 SQL 成功而 RAG 工具错误。

## 7. RAG 数据身份边界

当前 searchable document 使用稳定业务身份：

```text
(domain, dataset_id, source_id)
```

正式 Enterprise Retail：

```text
domain = enterprise_retail
```

历史 Recipe：

```text
domain = recipe
```

这样可以避免同一个 PGVector corpus 中跨业务域误召回。

## 8. 当前能力停止线

除非出现阻塞 Enterprise Demo、正式 Eval 或核心发布的真实 bug，否则不再继续扩展以下模块：

- Router 核心分类体系
- Planner 主要职责边界
- 三个 canonical tools
- SQL 安全主链
- PGVector canonical RAG
- Graph predefined/dynamic 策略
- 默认五服务 Docker topology

后续工作重点应转向：

```text
文档
→ 演示
→ 面试表达
→ 评估结果解释
→ 针对真实 failure class 做最小修复
```

## 9. 不应过度声称

不能把当前项目描述为：

- 生产级高可用平台
- 完整 RBAC / SSO / 多租户数据平台
- 完整依赖感知式多跳 scheduler
- 严格 grounded faithfulness 已验证系统
- 固定低延迟 SLA 系统
- 所有 legacy 代码均已删除

准确边界见 [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)。
