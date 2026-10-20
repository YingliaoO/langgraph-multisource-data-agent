# Multi-Source Data Agent 当前已知限制

## 1. 本文目的

本文用于限制公开表述，避免把一个完成度较高的求职/工程 Demo 包装成不存在的生产能力。

## 2. 没有完整依赖感知式多跳 scheduler

Planner 可以产生多个 task，并表达 `depends_on` 字段，无依赖任务可以并行执行。

但当前不应声称已经实现：

```text
A 输出动态决定 B 输入
B 阻塞等待 A
运行时 DAG 重排
复杂 conditional scheduling
```

当前最成熟的是“独立子任务并行 + Evidence Fusion”。

## 3. LangGraph checkpoint 仍是 MemorySaver

当前 checkpoint 是进程内存：

- 进程重启会丢失 Graph checkpoint。
- 多 worker 之间不共享 checkpoint。
- SQL 聊天历史持久化不等于完整恢复 LangGraph state。

生产化多实例可以考虑 PostgreSQL/Redis backed checkpointer，但当前 Demo 不需要为此引入新基础设施。

## 4. 不是生产级高可用

当前验证了：

- Docker 五服务运行
- liveness/readiness
- timeout/retry
- structured error
- Eval

没有验证：

- multi-replica failover
- autoscaling
- cross-region HA
- production service mesh
- fleet circuit breaker

## 5. LLM Provider 仍是外部依赖

Router、Planner、生成和部分工具内部逻辑仍依赖外部 LLM。

可能出现：

- latency spikes
- provider outage
- rate limit
- billing/credit exhaustion

当前会记录 timeout/fallback，但不能消除外部依赖风险。

## 6. 结构化输出存在 long-tail

实际基线观察到 Router structured-output 请求可能触发 60 秒 timeout；Tool 也出现过 100 秒 budget timeout。

不能通过简单提高 60/100/300 秒预算来声称问题已解决。

## 7. Eval 样本规模有限

当前正式 Enterprise dataset 只有 12 个 case，适合固定核心回归，但不能代表所有企业查询分布。

## 8. Grounded faithfulness 尚未严格自动评估

当前已有：

- Evidence availability
- expected fact support
- citation lineage
- fact coverage

但没有严格 LLM judge + 人工标注协议，因此不能说“答案已通过严格 faithfulness benchmark”。

## 9. Literal fact matcher 有语言局限

首版 Enterprise Eval 中 `1 business day` 与中文“1 个工作日”出现字面匹配差异。

这是 evaluator limitation，不应当作 RAG 检索失败。

## 10. File-query 只有 submission acknowledgement

当前 file upload：

```text
POST upload
→ file-query
→ Background ingestion submission
```

没有完整 job lifecycle：

- job_id 统一状态查询
- progress
- failure polling
- user-visible retry

因此不能说 file-query success 等于后台已完成并可查询。

## 11. RAG 未知数据集的 identity 是 content-addressed

未知文件且调用方不传 stable `dataset_id` 时：

```text
相同内容 → 相同 dataset
内容变化 → 新 dataset
```

只有显式/fixed dataset_id 才表达“同一个 logical dataset 的新版本”。

## 12. 无自然业务主键 CSV 的 row-number fallback

如果记录没有 `source_id/doc_id/id/sku/record_id` 等可用业务主键，会退回稳定行号。

因此：

```text
内容变化但行位置不变 → 可更新
行重新排序 → 无法保证 logical identity 不变
```

当前作为明确 limitation 保留，不进一步引入复杂 record matching。

## 13. Auth / RBAC / 多租户未实现

当前没有完整：

- SSO
- RBAC
- tenant isolation
- row-level access policy
- enterprise audit permission

用户提交 `user_id` 的方式不能当成生产认证。

## 14. 数据上传边界仍是 Demo 级

已有扩展名、大小等基础限制，但没有完整：

- MIME sniffing
- virus scan
- per-tenant quota
- content security scanning
- background job governance

## 15. Legacy 代码仍存在

部分旧 route alias 和兼容源码仍存在；Milvus/LightRAG 运行资产及 Recipe 数据、词典没有纳入公开快照。

准确表述：

> 已退出默认产品路径和主叙事。

不要说：

> 已从代码库彻底删除。

## 16. Graph fallback 可能影响效率

GraphTool 内部 predefined 与 dynamic Text2Cypher 的 fallback 可能成功但增加 latency。

成功 + fallback 不等于 correctness failure。

## 17. 测试与运行验证边界

当前快照：

```text
183 passed
```

公开快照排除了依赖未确认授权历史资产的 legacy 测试；上述结果仅覆盖随快照分发的测试。Docker、外部模型调用与端到端 smoke 需另行验证。

## 18. Readiness 不等于全链路事务验证

`/ready` 检查关键依赖，但不能证明每一个内部子系统、每个数据集、每个外部 provider 操作都成功。

## 19. 合成数据边界

Enterprise Retail 是 synthetic dataset，不允许包装成真实公司生产指标、真实客户数据或真实业务验证。

## 20. 公开表述建议

可以说：

> “完成了可解释、可评测的多源 Data Agent 工程链路，并对 SQL 安全、Evidence contract、RAG identity、timeout/fallback 做了明确工程边界。”

不要说：

> “已经达到生产级企业智能数据平台标准。”
