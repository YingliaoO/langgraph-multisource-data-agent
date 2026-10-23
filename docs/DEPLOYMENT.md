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

从旧版配置升级时，请将项目专属变量改名：`GUSTOBOT_DEBUG` → `MULTISOURCE_AGENT_DEBUG`，`GUSTOBOT_MEMORY_TURNS` → `MULTISOURCE_AGENT_MEMORY_TURNS`。可选的 CLI 兼容参数 `GUSTOBOT_MAX_MEMORY_TURNS` 和测试地址 `GUSTOBOT_BASE_URL` 分别改为 `MULTISOURCE_AGENT_MAX_MEMORY_TURNS`、`MULTISOURCE_AGENT_BASE_URL`。`DEBUG`、`LLM_BASE_URL` 等通用变量无需改名。默认 SQLite 文件名保留 `data/gustobot.db` 以兼容已有数据，不执行隐式数据库迁移。

### 修改 `.env` 后让配置生效

Compose 的 `environment` 在创建容器时注入。修改主机 `.env` 或执行 `docker compose restart backend`，不会更新已有容器的这部分环境变量；应用读取挂载的 `.env` 时，容器中旧环境变量还可能优先于新文件。

确认 `DATABASE_URL` 指向正确的 MySQL 服务、数据库和有效账号后，重建后端容器：

```powershell
docker compose config --quiet
docker compose up -d --no-deps --force-recreate backend
curl.exe -s http://localhost:8000/ready
```

若修改的是 `KB_EMBEDDING_*`、`KB_LLM_*` 等知识服务配置，还需运行 `docker compose up -d --no-deps --force-recreate kb_ingest`，再检查 `http://localhost:8100/health` 及真实检索。只重建 backend 不会更新 kb_ingest 容器中的旧环境变量。

若同时修改了依赖或 Dockerfile，先运行 `docker compose build backend`。上述操作保留 MySQL、Neo4j 和 PGVector 的现有数据卷，不需要执行 `down -v`、重新导入数据或重置数据库密码。不要把包含凭据的完整 `docker compose config` 输出贴到公开日志中。

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

`llm_config=ok` 表示已配置模型密钥，不会向外部模型服务发起付费认证请求。因此 `/ready` 为 200 时，真实聊天仍可能收到提供方的 401 `invalid_api_key` 或 404 `model_not_found`。前者需要在本机检查密钥与服务地址是否匹配；后者需要确认 `LLM_MODEL` 是该服务及账号实际可用的模型。更新 `.env` 后重建后端容器，再用真实聊天请求验证，切勿将密钥贴入日志或聊天。

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

测试数量随代码版本变化，最近的执行日期、范围和结果见[验证记录](VALIDATION.md)。

如果误用系统 Python 出现 NumPy/Pandas ABI 或缺包问题，先确认解释器：

```powershell
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable)"
```

## 10. Enterprise Smoke

```powershell
.\.venv\Scripts\python.exe -u .\demo\enterprise_retail\smoke.py
```

Smoke 覆盖六项检查。应以当前环境的逐项输出判定通过情况；HTTP 200、文件提交确认或单元测试通过都不能代替完整 Smoke 验收。最近的部分真实请求结果见[验证记录](VALIDATION.md)。

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

评测报告应记录实际模型、timeout/retry 配置及失败结果。配置不同的运行应单独报告，避免混合比较。

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

这些能力需要独立的实现与验证，当前本地演示不具备上述生产保证。
