"""Generate grounded Data Agent answers from a bounded EvidenceContext."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from .evidence_context import EvidenceContext


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Multi-Source Data Agent, an enterprise data agent.
Answer only from the supplied EvidenceContext. Use structured SQL and graph facts for
data claims, and document facts for knowledge explanations. Never invent a result,
relationship, source, citation, score, or conclusion absent from the context.
Tool answers may be generated text and are not independent evidence; distinguish them
from sourced document facts. Mention when the context is truncated or a tool failed.
If evidence is insufficient, say so clearly. Respond in the language of the task
when apparent, otherwise in Chinese. Keep the answer concise and useful.
When citation evidence is supplied, return only evidence IDs that materially support
the answer; never invent an evidence ID."""


class AnswerSynthesis(BaseModel):
    answer: str
    citation_ids: list[str] = Field(default_factory=list)


def render_sections(
    narrative: list[str], metric: list[str], errors: list[str]
) -> str:
    """Preserve the current deterministic answer format for fallback."""
    sections: list[str] = []
    if narrative:
        sections.append("### \u5ddd\u83dc\u6982\u89c8\n" + "\n\n".join(narrative))
    if metric:
        sections.append("### \u6570\u636e\u7edf\u8ba1\n" + "\n\n".join(metric))
    if errors:
        sections.append("### \u67e5\u8be2\u63d0\u793a\n" + "\n".join(f"- {item}" for item in errors))
    return "\n\n".join(section for section in sections if section).strip() or "No data to summarize."


def _prompt_payload(context: EvidenceContext) -> str:
    # Facts and metadata are already bounded by the EvidenceContext Builder.
    payload = {
        "sql_facts": context.sql_facts,
        "graph_facts": context.graph_facts,
        "document_facts": context.document_facts,
        "tool_answers": context.tool_answers,
        "citation_evidence": context.citation_facts,
        "metadata": context.metadata,
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _valid_citation_ids(context: EvidenceContext, values: Any) -> list[str]:
    allowed = {
        str(item.get("evidence_id"))
        for item in context.citation_facts
        if isinstance(item, dict) and item.get("evidence_id")
    }
    citations: list[str] = []
    for value in values or []:
        candidate = str(value)
        if candidate in allowed and candidate not in citations:
            citations.append(candidate)
    return citations


async def generate_answer_with_citations(
    context: EvidenceContext, llm: Any
) -> tuple[str, list[str]]:
    """Generate one grounded answer and the evidence IDs actually used by it."""
    narrative, metric, errors = context.summary_sections()
    fallback = render_sections(narrative, metric, errors)
    fallback_citations = _valid_citation_ids(
        context, [item.get("evidence_id") for item in context.citation_facts]
    )
    if not (narrative or metric):
        return fallback, []

    structured = getattr(llm, "with_structured_output", None)
    if callable(structured):
        try:
            response = await structured(AnswerSynthesis).ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=_prompt_payload(context)),
            ])
            answer = response.answer if isinstance(response, AnswerSynthesis) else getattr(response, "answer", None)
            citation_ids = (
                response.citation_ids
                if isinstance(response, AnswerSynthesis)
                else getattr(response, "citation_ids", [])
            )
            if isinstance(answer, str) and answer.strip():
                return answer.strip(), _valid_citation_ids(context, citation_ids)
        except Exception as exc:
            logger.warning("Structured summarize unavailable; using bounded context fallback: %s", exc)

    # Keep compatibility with non-structured test/dummy models without adding a
    # second LLM call for normal ChatOpenAI execution.
    ainvoke = getattr(llm, "ainvoke", None)
    if callable(ainvoke) and not callable(structured):
        try:
            response = await ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=_prompt_payload(context)),
            ])
            answer = response if isinstance(response, str) else getattr(response, "content", None)
            if isinstance(answer, str) and answer.strip():
                return answer.strip(), fallback_citations
        except Exception as exc:
            logger.warning("Summarize LLM unavailable; using bounded context fallback: %s", exc)
    return fallback, fallback_citations


async def generate_answer(context: EvidenceContext, llm: Any) -> str:
    """Use the existing workflow LLM; retain deterministic output on failure."""
    narrative, metric, errors = context.summary_sections()
    fallback = render_sections(narrative, metric, errors)
    if not (narrative or metric):
        return fallback

    ainvoke = getattr(llm, "ainvoke", None)
    if not callable(ainvoke):
        return fallback

    try:
        response = await ainvoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_prompt_payload(context)),
        ])
        answer = response if isinstance(response, str) else getattr(response, "content", None)
        if isinstance(answer, str) and answer.strip():
            return answer.strip()
    except Exception as exc:
        logger.warning("Summarize LLM unavailable; using bounded context fallback: %s", exc)
    return fallback
