"""Answer-to-evidence citation lineage tests."""

import asyncio

from gustobot.application.agents.execution_contract import normalize_tool_results
from gustobot.application.agents.kg_sub_graph.agentic_rag_agents.components.summarize.answer_generator import (
    AnswerSynthesis,
    generate_answer_with_citations,
)
from gustobot.application.agents.kg_sub_graph.agentic_rag_agents.components.summarize.evidence_context import (
    build_evidence_context,
)
from gustobot.application.agents.tool_contracts import Evidence, ToolResult


class _StructuredInvoker:
    async def ainvoke(self, _messages):
        return AnswerSynthesis(
            answer="There is one matching row.",
            citation_ids=["ev_task_demo_1", "ev_missing_9", "ev_task_demo_1"],
        )


class _StructuredLLM:
    def with_structured_output(self, _schema):
        return _StructuredInvoker()


def _context():
    result = ToolResult(
        tool_name="sql_agent",
        tool_kind="sql",
        status="success",
        task="demo",
        evidence=[Evidence(kind="sql_row", content={"count": 1}, source="mysql")],
        metadata={"planner_task": {"task_id": "task-demo"}},
    )
    normalized = normalize_tool_results([result])
    return build_evidence_context(normalized), normalized[0].evidence_ids[0]


def test_answer_generator_keeps_only_real_used_evidence_ids() -> None:
    context, evidence_id = _context()
    assert evidence_id == "ev_task_demo_1"
    assert context.citation_facts[0]["evidence_id"] == evidence_id

    answer, citation_ids = asyncio.run(generate_answer_with_citations(context, _StructuredLLM()))

    assert answer == "There is one matching row."
    assert citation_ids == [evidence_id]


def test_answer_generator_fallback_cites_bounded_evidence() -> None:
    context, evidence_id = _context()

    answer, citation_ids = asyncio.run(generate_answer_with_citations(context, object()))

    assert "count" in answer
    assert citation_ids == [evidence_id]
