# 验证记录

日期：2026-10-23。范围为本地开发工作区的工程检查、部分真实 HTTP 请求和真实前端录制，未对应新的发布 tag，也不是完整的 12-case Eval baseline。

## 工程检查

| 检查 | 结果与范围 |
| --- | --- |
| Python 自动化测试（同日较早的全量运行） | 223 passed、0 failed、0 skipped；15 条依赖弃用警告；mock 外部模型和数据库 |
| 文档整理后的相关回归 | 13 passed；覆盖 Enterprise Retail 文档和产品范围约束，未重复整套测试 |
| 独立环境安装 | Python 3.12.7，按 README 安装依赖与项目，pip check 通过 |
| wheel 构建与隔离导入 | 通过；在仓库外从 site-packages 导入应用，版本 0.1.2 |
| 前端 lint/build | 通过；仍有 Sass legacy JS API 弃用提示 |
| Docker backend 镜像构建 | 通过；安装同一 pyproject 元数据并执行 pip check |
| Compose 配置 | 通过；配置检查与真实服务请求分别验收 |
| 文档与公开资源检查 | 18 份 Markdown、102 个本地链接、27 项忽略规则检查通过 |
| 新增演示素材 | 9 张真实提问 / 回答 / 证据截图、3 段原始 WebM；视频元数据及结尾画面解码核对通过 |

以上为对应范围的本地执行记录，不代表 GitHub Actions 的执行状态。测试数量会随代码版本变化。

## 真实前端录制验证

通过 Playwright 在独立的浏览器会话中打开 Vue 前端，填写问题并点击发送；请求由前端正常发往 Chat API，不拦截、回放或替换响应。模型为 qwen-max，runtime timeout/retry 未改动。

| 场景 | HTTP / route / 工具状态 | 实际事实 | Evidence / 引用 | 前端观测耗时 | Agent total_ms |
| --- | --- | --- | --- | ---: | ---: |
| SQL 订单计数 | 200 / data-query / sql_agent success | 12 个订单；statement.language=sql | 1 / 1 | 26.9 秒 | 25802.81 |
| Graph 商品供应商 | 200 / data-query / graph_tool success | NorthStar Electronics；statement.language=cypher | 1 / 1 | 13.5 秒 | 12715.14 |
| RAG 退货政策 | 200 / data-query / knowledge_rag success | 7 个自然日；source=pgvector | 1 / 1 | 22.4 秒 | 20840.57 |

三条响应均为 execution.contract_version=1、execution.status=success、fallback_reason=none；引用可解析到响应中的 Evidence。前端观测耗时为点击发送到读取真实响应的时间，与 Agent 内部 timings.total_ms 分开记录。

已保存每个场景的提问、回答及证据截图，并保存原始 WebM 录屏。录屏覆盖实际等待时间、无加速剪辑、无旁白；文件及逐项链接见[界面与示例](SHOWCASE.md)。这是三条单独演示请求，不代表完整 Smoke 或 Eval 通过，也不能证明历史长尾延迟已消失。

## 较早的服务恢复与 HTTP 排查

部署使用 MySQL、Neo4j、PGVector 和已有的合成零售数据；本次主模型与知识摄取模型均为 qwen-max。运行时 timeout/retry 未调整。

| 项目 | 实际结果 | 总耗时 |
| --- | --- | ---: |
| Backend readiness | HTTP 200，数据库、Neo4j、知识服务及模型配置检查通过 | — |
| 商品供应商查询 | HTTP 200、graph_tool=success、NorthStar Electronics、Cypher、1 条 Evidence | 24.5 秒 |
| 电子产品退货政策 | HTTP 200、knowledge_rag=success、7 个自然日、1 条 PGVector Evidence、1 个引用 | 42.9 秒 |
| SQL 订单计数 | 两次 HTTP 200、execution=error，均触发 100 秒工具超时 | 130.9 / 170.9 秒 |
| bootstrap 文件摄取 | 预期 file-query，实际返回 data-query，未通过验收 | — |

较早两次 SQL 超时发生在 schema 检索和查询分析完成后的 SQL 生成请求等待阶段，不能按数据库查询成功计分。后续前端录制中的 SQL 查询成功，不覆盖这两次失败记录。readiness 的模型配置检查只确认配置存在，不验证每个模型请求的可用性。

知识服务通过已有摄取 API 成功写入 6 条合成文档，使用 domain=enterprise_retail、dataset_id=enterprise_retail_knowledge_v1。该入库结果与后续 RAG 查询已确认，但不能代替 bootstrap 文件路由或完整 CSV Smoke 的验收。

本次未重新执行完整 12-case Eval、6-case Smoke 或自然提问补充集。分次诊断不合并为新的完整基线。原始请求产物保存在被 Git 忽略的 eval/results/ 中，不随仓库发布。

## 历史基线与指标解释

[Enterprise Retail v1 首轮 HTTP 报告](../eval/reports/enterprise_retail_v1_initial.md)保留原 12-case 历史分数、SQL 超时与中英文字面匹配偏差。确定性测试、部分真实请求和完整历史基线分别记录，不相互替代。

自然提问补充集与显式事实断言见[评测说明](EVALUATION.md#15-自然提问补充集与独立事实断言)。这些检查不等于严格的语义正确性或 grounded faithfulness 评估。
