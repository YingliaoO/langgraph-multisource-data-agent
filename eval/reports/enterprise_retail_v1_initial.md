# Enterprise Retail v1：首轮 HTTP Eval 摘要

这是对本地 `eval/results/enterprise_retail_v1/20260928_210302/` 原始产物的**脱敏摘录**，没有复制回答全文、文档内容、trace ID、请求头、凭据或环境路径。原始运行结果未作修改。Runner 通过真实 Chat HTTP API 请求完整 Agent，而不是直接调用工具函数。

- 运行日期：2026-09-28
- 用例：12 条（SQL 5、Graph 3、RAG 3、general control 1）
- 运行时工作区含未提交改动，因此不能仅凭单一提交版本完全复现这次结果。
- 运行时 dataset SHA-256：`641f8c8e13c5dcc6670ccae6aff0615f711c95f53c806f07323300c2f8df0c95`。当前仓库 dataset 的字节哈希不同；12 个 case 的问题、期望路由、工具、状态、事实及其他评测语义字段已逐项核对一致。
- Runner：请求超时 600 秒；transport retry 0 次。

| 指标 | 首轮值 |
| --- | ---: |
| HTTP 请求成功率 | 100% |
| Router 路由准确率 | 100% |
| Tool Selection 准确率 | 100% |
| Tool Execution 成功率 | 81.82% |
| Execution status 准确率 | 91.67% |
| Evidence availability 准确率 | 91.67% |
| 回答事实字面覆盖率 | 83.33% |
| 预期事实受 Evidence 支持率 | 77.78% |
| fallback rate | 16.67% |
| 平均总耗时 | 66.4 秒 |
| p95 总耗时 | 155.4 秒 |

逐 case 的 **期望状态 → 实际状态**：

| Case | 工具 | 状态 | Evidence 数 | 事实覆盖 | Evidence 支持 | 总耗时 |
| --- | --- | --- | ---: | ---: | --- | ---: |
| `enterprise_sql_order_count` | SQL | success → success | 1 | 100% | 是 | 52.2s |
| `enterprise_sql_category_units` | SQL | success → success | 4 | 100% | 是 | 25.2s |
| `enterprise_sql_customer_count` | SQL | success → error | 0 | 0% | 否 | 137.3s |
| `enterprise_sql_empty_order` | SQL | empty → empty | 0 | 不适用 | 不适用 | 40.8s |
| `enterprise_sql_policy_rejection` | SQL | error → error | 0 | 不适用 | 不适用 | 25.6s |
| `enterprise_graph_product_supplier` | Graph | success → success | 1 | 100% | 是 | 43.6s |
| `enterprise_graph_supplier_products` | Graph | success → success | 3 | 100% | 是 | 12.2s |
| `enterprise_graph_product_category` | Graph | success → success | 1 | 100% | 是 | 66.4s |
| `enterprise_rag_return_policy` | RAG | success → success | 1 | 100% | 是 | 114.3s |
| `enterprise_rag_supplier_sla` | RAG | success → success | 1 | 100% | 是 | 65.3s |
| `enterprise_rag_refund_sop` | RAG | success → success | 1 | 50% | 否 | 155.4s |
| `enterprise_general_control` | 无数据工具 | success → success | 0 | 不适用 | 不适用 | 58.5s |

`enterprise_sql_customer_count` 在工具层约 100 秒超时，因而没有产生预期事实或 Evidence。`enterprise_rag_refund_sop` 的回答与证据使用中文“1 个工作日”，而预期事实为英文 `1 business day`，字面评测未将二者视为同义；它的 50% 覆盖率不是“整个回答一半正确”的人工判断。另有两个 case 触发 Router timeout fallback，最终路由和工具仍符合期望。

本次结果只能作为**单轮历史基线**：100% 路由/工具选择不等于整体 Agent 100% 正确；字面事实匹配不是严格的事实忠实度判定。指标定义和分母规则见 [评测体系说明](../../docs/EVALUATION.md)。
