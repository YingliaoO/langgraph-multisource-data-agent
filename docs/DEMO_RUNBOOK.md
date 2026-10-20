# GustoBot Enterprise Retail 演示手册

## 1. 演示目标

演示 GustoBot 当前 Data Agent 主链，而不是展示历史 Chatbot/菜谱/多模态能力。

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

当前验证结果：

```text
enterprise_sql_order_count       PASS
enterprise_sql_category_units    PASS
enterprise_graph_supplier        PASS
enterprise_rag_refund_policy     PASS
enterprise_sql_policy_rejection  PASS
enterprise_file_ingestion        PASS

Enterprise smoke: 6/6 passed
```

## 10. 三条 Enterprise RAG 定向验证

建议单独验证：

```text
enterprise_rag_return_policy
enterprise_rag_supplier_sla
enterprise_rag_refund_sop
```

当前三条均可走：

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

## 12. 不推荐的演示方式

不要把主要时间花在：

- 老 Recipe Chatbot
- Milvus
- LightRAG API
- Vision/Image
- crawler
- Redis

这些不属于当前求职展示主线。

## 13. 演示异常时怎么讲

### Router timeout 但 fallback 后成功

准确说：

> Router structured output 有 provider long-tail，系统在 timeout 后使用 fallback，最终 route/tool/evidence 正确；该现象会计入 fallback 与 latency，而不是隐藏。

### Tool timeout

准确说：

> Tool 有独立 100 秒预算，超时会返回结构化 error，并记录 observed duration；不会无限等待或通过无限 retry 掩盖问题。

### RAG 中文/英文 literal mismatch

准确说：

> Answer 和 Evidence 语义正确，但首版 Eval 使用字面 expected fact matching，所以保留为 evaluator limitation。
