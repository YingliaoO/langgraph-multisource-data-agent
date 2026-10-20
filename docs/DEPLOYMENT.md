# Multi-Source Data Agent 当前部署说明

## 1. 部署目标

当前默认部署只围绕 Multi-Source Data Agent 主线：

```text
backend
mysql
neo4j
kb_postgres
kb_ingest
```

Milvus、Redis、LightRAG、Vision/Image 不应重新加入默认 Compose。

## 2. 系统要求

推荐开发环境：

- Docker Desktop / Docker Engine + Compose
- Python 3.12 对应项目 `.venv`
- Node.js / npm（仅 Web Console）
- Git

Windows PowerShell 是当前常用验证环境。

## 3. 环境配置

复制环境配置模板：

```powershell
Copy-Item .env.example .env
```

根据当前 `settings.py` / `.env.example` 填写：

- LLM OpenAI-compatible endpoint
- Embedding endpoint
- Reranker endpoint
- MySQL
- Neo4j
- PostgreSQL/PGVector

不要提交真实 `.env`。

从旧版配置升级时，请将项目专属变量改名：`GUSTOBOT_DEBUG` → `MULTISOURCE_AGENT_DEBUG`，`GUSTOBOT_MEMORY_TURNS` → `MULTISOURCE_AGENT_MEMORY_TURNS`。可选的 CLI 兼容参数 `GUSTOBOT_MAX_MEMORY_TURNS` 和测试地址 `GUSTOBOT_BASE_URL` 分别改为 `MULTISOURCE_AGENT_MAX_MEMORY_TURNS`、`MULTISOURCE_AGENT_BASE_URL`。`DEBUG`、`LLM_BASE_URL` 等通用变量无需改名。已有 `data/gustobot.db` 仍沿用原路径，本轮不迁移或删除数据库文件。

## 4. 启动核心服务

```powershell
docker compose up -d
```

查看：

```powershell
docker compose ps
```

预期服务：

```text
backend
mysql
neo4j
kb_postgres
kb_ingest
```

## 5. 健康检查

### Backend liveness

```powershell
curl.exe -s http://localhost:8000/health
```

### Backend readiness

```powershell
curl.exe -s http://localhost:8000/ready
```

`/ready` 应检查关键依赖，例如：

```text
database
neo4j
knowledge_service
llm_config
```

### kb_ingest

```powershell
curl.exe -s http://localhost:8100/health
```

## 6. Enterprise Retail 初始化

```powershell
.\.venv\Scripts\python.exe .\demo\enterprise_retail\bootstrap.py
```

初始化：

- MySQL retail tables
- Neo4j retail graph
- Enterprise Retail knowledge dataset

公开快照不包含 Recipe 初始化资产；bootstrap 只写入 Enterprise Retail 合成数据。

## 7. RAG startup migration

`kb_ingest` 启动时会确保 document identity schema：

```text
(domain,dataset_id,source_id)
```

已有 legacy 表时，startup migration 可进行：

- 列回填
- duplicate cleanup
- 联合唯一索引迁移

正常 `/search` 请求不应再执行重型迁移。

如果 migration 失败，推荐让服务启动失败并排查，而不是让每次 search 尝试修 schema。

## 8. Web Console

开发：

```powershell
npm --prefix .\web install
npm --prefix .\web run dev
```

构建：

```powershell
npm --prefix .\web run build
```

Web 不属于默认五服务 backend/data compose。

## 9. 运行测试

必须使用项目 `.venv`，避免系统 Anaconda/Python 包 ABI 污染。

```powershell
$env:DEBUG='false'
.\.venv\Scripts\python.exe -m pytest -q
```

当前快照：

```text
183 passed
```

如果误用系统 Python 出现 NumPy/Pandas ABI 或缺包问题，先确认解释器：

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

## 10. Enterprise Smoke

```powershell
.\.venv\Scripts\python.exe -u .\demo\enterprise_retail\smoke.py
```

当前预期：

```text
6/6 passed
```

## 11. 正式 Enterprise Eval

示例：

```powershell
.\.venv\Scripts\python.exe eval/run_eval.py `
  --dataset eval/datasets/enterprise_retail_v1.jsonl `
  --base-url http://localhost:8000 `
  --output-dir eval/results/enterprise_retail_v1 `
  --timeout 600 `
  --retry-count 0
```

不要因为 provider latency 临时修改 runtime timeout/retry 再跑“漂亮分数”。

## 12. 日志排查

### Backend

```powershell
docker compose logs -f backend
```

### kb_ingest

```powershell
docker compose logs -f kb_ingest
```

### MySQL

```powershell
docker compose logs -f mysql
```

### Neo4j

```powershell
docker compose logs -f neo4j
```

### PostgreSQL

```powershell
docker compose logs -f kb_postgres
```

## 13. 常见问题

### `/health` 正常但查询失败

检查 `/ready`。liveness 只说明 FastAPI 进程活着。

### RAG 查询返回 Recipe 文档

当前 Enterprise path 应带 `domain=enterprise_retail`。检查：

- KnowledgeRAGTool context
- search request filter
- searchable_documents domain

### 重复上传 weekly_campaign 出现重复数据

当前稳定 identity 应基于：

```text
(domain,dataset_id,source_id)
```

检查是否绕过 canonical ingestion API 或 dataset_id 不稳定。

### 第一次 search 很慢并出现 DDL

当前 migration 应在 startup，不应在 search path。若出现，说明运行容器可能仍加载旧代码。

### Agent 一直很慢

先区分：

```text
Router
Planner
Tool
AnswerGenerator
```

查看 trace/timings。不要直接把所有 timeout 放大。

## 14. 生产化前仍缺少的内容

当前部署不是生产级：

- Auth/RBAC
- tenant isolation
- persistent LangGraph checkpointer
- ingestion job lifecycle
- autoscaling/HA
- secret manager
- monitoring/alerting

这些属于未来生产化，而不是当前求职 Demo 必须堆叠的能力。
