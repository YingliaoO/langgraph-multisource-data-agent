# 文档索引

本公开快照面向 **Synthetic Enterprise Retail** 演示域。历史 Recipe 表格、词典、归档与评测集未随仓库分发。项目保留少量兼容类型和旧别名，默认运行链路仅使用 `data-query` 与三个 canonical tools。

建议从[项目首页](../README.md)开始，然后按需要阅读：

- [快速启动](QUICK_START.md)、[部署说明](DEPLOYMENT.md)：准备 `.env`、启动五个 Compose 服务、导入合成零售数据。
- [架构说明](ARCHITECTURE.md)、[产品边界](PRODUCT_SCOPE.md)：Router、Planner、工具执行、Evidence 和回答链路。
- [API 契约](API_CONTRACT.md)：`execution`、ToolResult、Evidence 与引用字段。
- [SQL 实现](TEXT2SQL_IMPLEMENTATION.md)：Text2SQL、SQLGlot、只读策略及受控修复。
- [零售演示](ENTERPRISE_RETAIL_DEMO.md)、[演示手册](DEMO_RUNBOOK.md)：合成数据与现场问题。
- [评测说明](EVALUATION.md)、[评测目录](../eval/README.md)：12 条正式 HTTP Eval 与历史基线的局限。
- [已知限制](KNOWN_LIMITATIONS.md)、[面试问答](INTERVIEW_GUIDE.md)、[开发说明](README_DEV.md)。

测试与真实 Docker smoke 的本次验证结果以发布前审核报告为准；文档内较早日期的运行数字是历史快照，不能当成本次重新执行的结果。