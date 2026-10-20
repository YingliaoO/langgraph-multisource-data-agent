# Enterprise Retail 评测

当前公开评测集为 [`datasets/enterprise_retail_v1.jsonl`](datasets/enterprise_retail_v1.jsonl)，包含 12 条合成企业零售 case。`run_eval.py` 使用与产品相同的 `POST /api/v1/chat/` HTTP 入口，优先读取正式 `response.execution`，并输出逐 case 与汇总指标。

先复制 `.env.example` 为 `.env`，填入您自己的 LLM、Embedding、Reranker 凭据，启动五个 Docker 服务，并运行 `demo/enterprise_retail/bootstrap.py` 初始化合成数据。然后在仓库根目录执行：

```powershell
python eval/run_eval.py --dataset eval/datasets/enterprise_retail_v1.jsonl --base-url http://localhost:8000 --output-dir eval/results/enterprise_retail_v1 --timeout 600 --retry-count 0
```

`eval/results/` 是被 Git 忽略的本地运行产物。公开仓库只保留[脱敏的首轮摘要](reports/enterprise_retail_v1_initial.md)；该摘要是 2026-09-28 的历史单轮结果，不是本公开快照的重新运行证明。指标口径、分母与超时解释见[评测说明](../docs/EVALUATION.md)。

原项目的 `core_v1` 是历史 Recipe 回归集，涉及来源未确认的数据与旧环境，本公开快照不分发它。不要把 12 条 case 的路由/工具选择准确率解读成整个 Agent 的正确率。