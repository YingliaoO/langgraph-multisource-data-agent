from langchain_core.prompts import ChatPromptTemplate

from gustobot.application.agents.kg_sub_graph.prompts.kg_prompts import PLANNER_SYSTEM_PROMPT


def create_planner_prompt_template() -> ChatPromptTemplate:
    """Create the generic Data Agent planner prompt template."""

    message = """规划规则：
- 将问题拆成最多 6 个不重复、可独立执行的证据获取任务。
- 每个任务只能给出一个 tool_hint：sql_agent、knowledge_rag、graph_tool 或 auto。
- sql_agent 面向关系型业务数据；knowledge_rag 面向文档知识；graph_tool 面向 Neo4j 关系/路径。
- 不要输出 text2sql_query、postgres、milvus、cypher_query、predefined_cypher、customer_tools 等旧工具名。
- depends_on 仅记录“证据上需要联合理解”的更早任务 ID；即使填写 depends_on，本任务问题也必须自包含，不能依赖运行时拿到前一步结果才能执行。
- task_id 使用 task_1、task_2 ...；依赖只能指向更早的 task_id。
- 简单问题只保留一个任务，不要为了拆解而拆解。
- 顶层 route 只是兼容性提示，不应覆盖更明确的数据来源判断。

顶层 route: {route_type}
用户问题: {question}
"""
    message += """

工具判断示例：
- “Aurora ANC Headphones 由哪个供应商供货？” -> 一个任务，tool_hint=`graph_tool`。
- “NorthStar Electronics 提供哪些商品？” -> 一个任务，tool_hint=`graph_tool`。
- “电子产品无质量问题几天可以退货？” -> 一个任务，tool_hint=`knowledge_rag`。
- “退款率超过 15% 后应该执行什么处理流程？” -> 一个任务，tool_hint=`knowledge_rag`。
- “当前 retail_orders 一共有多少个订单？” -> 一个任务，tool_hint=`sql_agent`。
- “按商品品类统计销售件数并排序” -> 一个任务，tool_hint=`sql_agent`。

商品与供应商、分类、活动之间的关系属于图谱证据；政策、SOP、活动规则和 SLA 属于文档证据；订单、销售和退款聚合属于关系型业务证据。不要把业务领域关键词直接当成工具选择规则。
"""

    return ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", message),
        ]
    )
