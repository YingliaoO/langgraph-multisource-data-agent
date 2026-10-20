# Multi-Source Data Agent 当前开发指南

## 1. 开发原则

当前项目已经完成主架构收敛，开发应优先：

```text
修真实 bug
→ 写回归测试
→ 跑 Enterprise Eval
→ 保持产品边界
```

不应为了“技术栈丰富”继续加入新的 Agent、向量库或基础设施。

## 2. 推荐环境

- Python 3.12 项目 `.venv`
- Docker Compose
- Node.js/npm
- Windows PowerShell 或 Linux shell

Windows 下建议显式调用：

```powershell
.\.venv\Scripts\python.exe
```

避免误用系统 Anaconda 导致包 ABI/依赖冲突。

## 3. 启动 backend/data services

```powershell
docker compose up -d
```

检查：

```powershell
docker compose ps
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/ready
curl.exe -s http://localhost:8100/health
```

## 4. 启动前端

```powershell
npm --prefix .\web install
npm --prefix .\web run dev
```

## 5. 代码分层理解

建议按下面顺序阅读：

```text
multisource_data_agent/interfaces/http/v1/chat.py
→ lg_builder.py / routing.py
→ planner / tool selection
→ tool_execution/interface.py
→ sql_agent.py / knowledge_rag.py / graph_tool.py
→ tool_contracts.py
→ execution_contract.py
→ eval/
```

## 6. 修改 Router 时

必须回答：

- 这是产品 route 问题，还是 tool selection 问题？
- 是否应该新增 Eval case？
- 是否会破坏 general/additional/file？
- 是否只是为了单个关键词打补丁？

禁止用无边界关键词硬编码代替语义路由。

## 7. 修改 Planner 时

当前 Planner 的核心职责：

```text
问题拆解
任务描述
depends_on 表达
```

不要把 SQL/Cypher generation 重新塞回 Planner。

## 8. 修改 Tool 时

三个 canonical tool 都必须返回统一 ToolResult。

检查：

```text
status
statement
data
evidence
evidence_ids
metadata
error_category
```

不要新增第四个 tool 来暴露某个内部策略。

## 9. 修改 SQLAgent 时

必须保持：

```text
SQLGlot
read-only
table/column safety
ambiguity validation
LIMIT
timeout
max 1 repair
repair 后 revalidate
```

policy rejection 不可通过 retry 绕过。

## 10. 修改 RAG 时

必须保持：

```text
PGVector canonical path
domain filter
stable dataset identity
(source domain,dataset_id,source_id)
incremental dedup
```

不要把 LightRAG/Milvus重新加入默认 tool registry。

## 11. 修改 RAG identity migration 时

重型 schema migration 应在 `kb_ingest` startup，normal search path 不做 DDL/duplicate cleanup。

writer 可以做轻量 schema assertion，但不应重复跑重型 migration。

## 12. 修改 API 时

`ChatResponse.execution` 是正式契约。

禁止让新 UI/Eval 依赖：

```text
完整 agent_state
递归 debug metadata
内部 prompt
```

新字段如影响公共接口，应考虑 `contract_version`。

## 13. 测试

### 全量

```powershell
$env:DEBUG='false'
.\.venv\Scripts\python.exe -m pytest -q
```

当前基线：

```text
183 passed
```

### 关键测试组

```text
test_semantic_router.py
test_generic_planner.py
test_canonical_tool_selection.py
test_text2sql_boundary.py
test_sql_semantic_safety.py
test_sql_controlled_repair.py
test_knowledge_rag_boundary.py
test_graph_tool_boundary.py
test_execution_contract.py
test_http_execution_contract.py
test_chat_api.py
test_eval_metrics.py
test_eval_latency_observability.py
test_rag_domain_isolation.py
test_dataset_ingestion_scope.py
```

## 14. Eval

代码单测通过后，如果修改 Agent 行为，再运行 Enterprise Eval：

```text
eval/datasets/enterprise_retail_v1.jsonl
```

不要修改 expected facts 来适配当前回答。

## 15. Git 规范

提交前：

```powershell
git diff --check
git status --short
git diff --cached --stat
```

不要提交：

- `.env`
- `eval/results/`
- 临时 patch/zip
- 本地绝对路径
- 调试 body/response
- secret

## 16. 文档同步

以下变化必须同步文档：

- Route/Tool contract
- Execution DTO
- Eval dataset/metrics
- Docker service topology
- Enterprise demo data facts
- RAG identity semantics
- Known limitations

## 17. 停止线

除非有真实核心失败，不主动增加：

- Redis
- Kafka
- Kubernetes
- 第四个 Agent Tool
- HyDE
- 新向量库
- 复杂 scheduler
- EXPLAIN optimizer

先把已有设计讲清楚，比继续堆功能更有求职价值。
