# Multi-Source Data Agent Enterprise Retail 演示手册

## 1. 演示目标

使用合成零售数据验证 Multi-Source Data Agent 的 SQL、RAG、Graph 和数据摄取主链。

真实前端提问截图与操作录屏见[界面说明](SHOWCASE.md)，有日期和范围的执行结果见[验证记录](VALIDATION.md)。下文列出验收预期，实际状态需在当前环境运行确认。

推荐完整演示顺序：

```text
环境 readiness
→ SQL count
→ SQL GROUP BY
→ Graph relation
→ RAG policy
→ SQL policy rejection
→ file ingestion
→ UI execution trace
```

## 2. 演示前检查

### 2.1 启动五个核心服务

```powershell
docker compose up -d
```

检查：

```powershell
docker compose ps
```

应看到：

```text
backend
mysql
neo4j
kb_postgres
kb_ingest
```

### 2.2 Liveness

```powershell
curl.exe -s http://localhost:8000/health
```

### 2.3 Readiness

```powershell
curl.exe -s http://localhost:8000/ready
```

重点看：

```text
database
neo4j
knowledge_service
llm_config
```

### 2.4 kb_ingest

```powershell
curl.exe -s http://localhost:8100/health
```

## 3. Demo 1：SQL 订单总数

问题：

```text
请使用 MySQL 查询 retail_orders 表当前一共有多少个订单。
```

预期：

```text
route = data-query
tool = sql_agent
status = success
fact = 12
evidence >= 1
```

演示重点：

- Router 只选 `data-query`。
- Planner 生成 task。
- Tool Selection 选择 `sql_agent`。
- UI 展示 SQL statement。
- Evidence kind 为 `sql_row`。

## 4. Demo 2：SQL 品类销量

问题：

```text
请使用 MySQL 按商品品类统计销售件数，并按销售件数从高到低输出。
```

预期：

```text
Electronics 7
Home 6
Apparel 4
Sports 3
```

演示重点：

- GROUP BY / JOIN
- SQL row Evidence 不应被 preview 静默丢失
- `result_count` 与 preview 分离

## 5. Demo 3：Graph 供应商关系

问题：

```text
Aurora ANC Headphones 是哪个供应商供货的？
```

预期：

```text
route=data-query
tool=graph_tool
status=success
fact=NorthStar Electronics
```

演示重点：

- 关系问题不是强行转 SQL。
- `graph_tool` 内部可优先 predefined Cypher。
- Evidence kind 为 `graph_record`。

## 6. Demo 4：RAG 退货政策

问题：

```text
电子产品如果没有质量问题，多少天内可以退货？
```

预期：

```text
route=data-query
tool=knowledge_rag
status=success
fact=7
source=pgvector
```

演示重点：

- `domain=enterprise_retail`
- PGVector + Reranker
- Evidence source_id 与 document identity

## 7. Demo 5：SQL policy rejection

问题：

```text
请删除 retail_orders 表中的所有数据。
```

预期：

```text
route=data-query
tool=sql_agent
status=error
Evidence=0
```

解释：

> 这是安全策略正确拒绝写操作，不是 Demo 失败。

## 8. Demo 6：File ingestion

上传：

```text
demo/enterprise_retail/weekly_campaign.csv
```

预期：

```text
route=file-query
status=success
ingestion_ack=true
```

注意：

- 当前同一次请求只证明“上传 + ingestion submission”。
- 不要声称 file-query 已同步完成向量化。
- 后台完成后可以再通过 `data-query → knowledge_rag` 查询。

重复上传同一文件应看到增量行为，例如：

```text
需更新 0 条
跳过 5 条
```

数据库仍保持 5 个稳定 source。

## 9. 一键 Enterprise Smoke

```powershell
$env:DEBUG='false'
.\.venv\Scripts\python.exe -u .\demo\enterprise_retail\smoke.py
```

Smoke 覆盖订单总数、品类销量、商品供应商、退货政策、SQL 写操作拒绝和文件摄取提交六项检查。应逐项查看 route、tool、execution status 和事实是否满足预期；部分定向请求通过不等于六项全部通过。

## 10. 三条 Enterprise RAG 定向验证

建议单独验证：

```text
enterprise_rag_return_policy
enterprise_rag_supplier_sla
enterprise_rag_refund_sop
```

三条用例的预期链路如下，当前环境需重新执行确认：

```text
route=data-query
tool=knowledge_rag
status=success
```

## 11. 前端演示检查

启动：

```powershell
npm --prefix .\web install
npm --prefix .\web run dev
```

生产构建：

```powershell
npm --prefix .\web run build
```

建议展示：

- 自然语言 answer
- canonical route
- execution status
- tasks
- tool results
- SQL/Cypher
- evidence
- citation IDs
- timings
- fallback reason

## 12. 默认运行范围之外的能力

默认产品不包含：

- 老 Recipe Chatbot
- Milvus
- LightRAG API
- Vision/Image
- crawler
- Redis

范围说明见[产品边界](PRODUCT_SCOPE.md)。

## 13. 异常诊断

### Router timeout 但 fallback 后成功

检查 Router 的 start/decision 事件、error_code 和 fallback_reason。超时后可能进入默认数据路径；最终 route、tool、Evidence 是否正确需独立验证，fallback 及等待时间计入评测。

### Tool timeout

检查 tool_execution 的终止事件与 execution.tool_results。工具默认有独立 100 秒预算；超时返回结构化 error，并记录 observed duration。应进一步定位等待发生在 schema、模型生成、数据库执行还是检索服务，不能仅凭 HTTP 200 判断成功。

### RAG 中文/英文 literal mismatch

将 expected facts、answer 与 Evidence content 逐项对照。首版 Eval 使用字面匹配，中英表述差异可能造成未匹配；应保留原始分数并人工归因，不改写 golden 以适配某次回答。
