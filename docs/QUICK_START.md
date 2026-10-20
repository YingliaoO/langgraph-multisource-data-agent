# Multi-Source Data Agent 当前快速启动指南

## 1. 你将启动什么

默认运行时只有五个核心 backend/data 服务：

```text
backend
mysql
neo4j
kb_postgres
kb_ingest
```

当前默认业务域：Synthetic Enterprise Retail。

## 2. 准备 `.env`

```powershell
Copy-Item .env.example .env
```

填入必要的：

- LLM API
- Embedding API
- Reranker API
- 数据库配置

不要把真实 secret 提交 Git。

## 3. 启动 Docker

```powershell
docker compose up -d
```

检查：

```powershell
docker compose ps
```

## 4. 检查服务

```powershell
curl.exe -s http://localhost:8000/health
curl.exe -s http://localhost:8000/ready
curl.exe -s http://localhost:8100/health
```

只有 `/ready` 能说明关键依赖已满足请求条件。

## 5. 初始化 Enterprise Retail

如当前环境尚未初始化：

```powershell
.\.venv\Scripts\python.exe .\demo\enterprise_retail\bootstrap.py
```

## 6. 运行 Smoke

```powershell
.\.venv\Scripts\python.exe -u .\demo\enterprise_retail\smoke.py
```

当前预期：

```text
6/6 passed
```

## 7. 手工测试 Chat API

示例请求（具体请求字段以 OpenAPI 为准）：

```powershell
curl.exe -X POST "http://localhost:8000/api/v1/chat/" `
  -H "Content-Type: application/json" `
  -d '{"message":"请使用 MySQL 查询 retail_orders 表当前一共有多少个订单。"}'
```

重点检查响应：

```text
route
message
execution.contract_version
execution.status
execution.tool_results
execution.evidence
execution.timings
```

## 8. 推荐的四个数据问题

### SQL

```text
请使用 MySQL 查询 retail_orders 表当前一共有多少个订单。
```

### Graph

```text
Aurora ANC Headphones 是哪个供应商供货的？
```

### RAG

```text
电子产品非质量问题多少天内可以退货？
```

### General

```text
你好，你能做什么？
```

## 9. Policy Rejection

```text
请删除 retail_orders 表中的所有数据。
```

正确结果是 SQL 工具返回结构化 error，而不是执行写操作。

## 10. 上传 CSV

使用前端上传：

```text
demo/enterprise_retail/weekly_campaign.csv
```

或者通过当前 upload API。

正确理解：

```text
file-query success
= 导入任务已提交
≠ 后台向量化一定完成
```

## 11. 启动前端

```powershell
npm --prefix .\web install
npm --prefix .\web run dev
```

生产构建：

```powershell
npm --prefix .\web run build
```

## 12. 运行 Python 测试

```powershell
$env:DEBUG='false'
.\.venv\Scripts\python.exe -m pytest -q
```

当前快照：

```text
183 passed
```

## 13. 正式 Eval

```powershell
.\.venv\Scripts\python.exe eval/run_eval.py `
  --dataset eval/datasets/enterprise_retail_v1.jsonl `
  --base-url http://localhost:8000 `
  --output-dir eval/results/enterprise_retail_v1 `
  --timeout 600 `
  --retry-count 0
```

Eval 比 unit test 更慢，因为它真实调用 HTTP、LLM 和数据服务。

## 14. 常见故障

### Docker Desktop 未启动

`docker compose ps` 如果无法连接 named pipe，先启动 Docker Desktop。

### `.venv` 与系统 Python 混用

Windows 下明确使用：

```powershell
.\.venv\Scripts\python.exe
```

### RAG 数据未命中

检查：

```text
kb_ingest health
domain=enterprise_retail
dataset 是否已摄取
Embedding/Reranker endpoint
```

### 很慢

查看 `execution.timings` 和 trace，先判断是 Router、Tool 还是 AnswerGenerator，不要立即调大 timeout。
