"""Deterministic checks for optional, explicitly declared Eval facts."""

import csv
import json
from pathlib import Path

import pytest

from eval.evaluators.fact_assertions import evaluate_fact_assertions
from eval.evaluators.metrics import evaluate_case, summarize_results
from eval.run_eval import collect_environment_metadata, load_cases


ROOT = Path(__file__).resolve().parents[1]


def response(answer="", rows=(), source="mysql"):
    return {
        "message": answer,
        "execution": {
            "evidence": [{"source": source, "content": row} for row in rows],
        },
    }


def fact(kind="answer_fact", values=None, **kwargs):
    return {"id": "fact", "kind": kind, "any_of": values or ["5"], **kwargs}


@pytest.mark.parametrize("answer", ["15", "50", "5.5", "-5", "5e3", "1e5", "1,005", "5,000"])
def test_numeric_fact_does_not_match_another_number(answer):
    case = {"expected_key_facts": ["5"], "fact_assertions": [fact()]}
    result = evaluate_case(case, response(answer), 1)
    assert result["metrics"]["fact_coverage"] == 1.0  # historical literal semantics preserved
    assert result["metrics"]["asserted_fact_coverage"] == 0.0
    assert result["metrics"]["asserted_facts_ok"] is False


def test_numeric_fact_matches_chinese_context():
    assert evaluate_fact_assertions([fact()], response("共有5位客户。"))[0]["passed"]


def test_language_equivalence_requires_explicit_aliases():
    actual = response("请在 1 个工作日 内启动根因调查。")
    assert not evaluate_fact_assertions([fact(values=["1 business day"])], actual)[0]["passed"]
    assert evaluate_fact_assertions([fact(values=["1 business day", "1 个工作日"])], actual)[0]["passed"]


def category_assertions():
    return [
        {
            "id": category,
            "kind": "evidence_row",
            "source": "mysql",
            "fields": [
                {"keys": ["category", "品类"], "equals": category},
                {"keys": ["units", "销量"], "equals": units},
            ],
        }
        for category, units in [("Electronics", 7), ("Home", 6)]
    ]


def test_aggregate_values_cannot_be_swapped_or_joined_across_rows():
    swapped = response(rows=[{"category": "Electronics", "units": 6}, {"category": "Home", "units": 7}])
    assert not any(item["passed"] for item in evaluate_fact_assertions(category_assertions(), swapped))
    split = response(rows=[{"category": "Electronics"}, {"units": 7}])
    assert not evaluate_fact_assertions(category_assertions(), split)[0]["passed"]


def test_correct_rows_accept_explicit_field_aliases_and_decimal_strings():
    actual = response(rows=[{"品类": "Electronics", "销量": "7.0"}, {"category": "Home", "units": 6}])
    assert all(item["passed"] for item in evaluate_fact_assertions(category_assertions(), actual))


def test_conflicting_field_aliases_do_not_cherry_pick_a_matching_value():
    actual = response(rows=[{"category": "Electronics", "units": 6, "销量": 7}])
    assert not evaluate_fact_assertions(category_assertions(), actual)[0]["passed"]


def test_evidence_checks_use_canonical_content_and_source_only():
    assertion = fact("evidence_fact", ["48 hours"], source="pgvector")
    actual = response(rows=["48 hours"], source="mysql")
    actual["metadata"] = {"agent_state": {"evidence": [{"source": "pgvector", "content": "48 hours"}]}}
    assert not evaluate_fact_assertions([assertion], actual)[0]["passed"]
    assert evaluate_fact_assertions([assertion], response(rows=["48 hours"], source="pgvector"))[0]["passed"]


def test_single_column_aggregate_is_numeric_without_depending_on_sql_alias():
    assertion = {"id": "count", "kind": "evidence_scalar", "source": "mysql", "equals": 12}
    assert evaluate_fact_assertions([assertion], response(rows=[{"任意SQL别名": "12"}]))[0]["passed"]
    assert not evaluate_fact_assertions([assertion], response(rows=[{"count": 120}]))[0]["passed"]
    assert not evaluate_fact_assertions([assertion], response(rows=[{"id": 12, "count": 99}]))[0]["passed"]
    with pytest.raises(ValueError, match="numeric"):
        evaluate_fact_assertions([{**assertion, "equals": "12"}], response())


def test_assertions_missing_response_fail_but_absent_assertions_are_not_applicable():
    failed = evaluate_case({"fact_assertions": [fact()]}, None, 10, error="timeout")
    absent = evaluate_case({}, response(), 1)
    assert failed["metrics"]["asserted_facts_ok"] is False
    assert absent["metrics"]["asserted_facts_ok"] is None
    summary = summarize_results([failed, absent])
    assert summary["asserted_facts_ok_rate"] == 0.0
    assert summary["cases_with_fact_assertions"] == 1


def test_invalid_assertions_fail_fast_before_eval_request(tmp_path):
    dataset = tmp_path / "invalid.jsonl"
    dataset.write_text(json.dumps({"query": "q", "fact_assertions": [{"id": "x", "kind": "typo"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown assertion kind"):
        load_cases(dataset, [])
    with pytest.raises(ValueError, match="unique"):
        evaluate_fact_assertions([fact(), fact()], response())


def test_supplement_has_six_natural_cases_and_independent_multisource_task():
    cases = load_cases(ROOT / "eval/datasets/enterprise_retail_natural_v1.jsonl", [])
    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == 6
    for case in cases:
        assert case["fact_assertions"]
        assert not any(token in case["query"] for token in ["MySQL", "Neo4j", "SQL", "知识库", "PGVector"])
        assert all((ROOT / source).is_file() for source in case["fact_sources"])
    mixed = next(case for case in cases if len(case["expected_tools"]) == 2)
    assert mixed["expected_tools"] == ["sql_agent", "knowledge_rag"]


def test_supplement_aggregate_goldens_match_shipped_synthetic_seed():
    # Execute the INSERT statements in SQLite, independent of the evaluator,
    # to check all category/value pairs and count against the published seed.
    import re
    import sqlite3

    seed = (ROOT / "demo/enterprise_retail/mysql_seed.sql").read_text(encoding="utf-8")
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE retail_products (sku, name, category, supplier, price, active)")
        db.execute("CREATE TABLE retail_order_items (order_id, sku, quantity, price)")
        for table in ["retail_products", "retail_order_items"]:
            db.executescript(re.search(rf"INSERT INTO {table} VALUES.*?;", seed, re.S).group())
        counts = dict(db.execute("SELECT category, SUM(quantity) FROM retail_order_items JOIN retail_products USING (sku) GROUP BY category"))
    cases = load_cases(ROOT / "eval/datasets/enterprise_retail_natural_v1.jsonl", [])
    aggregation = next(case for case in cases if case["id"] == "natural_sql_category_units")
    expected = {item["fields"][0]["equals"]: item["fields"][1]["equals"] for item in aggregation["fact_assertions"]}
    assert expected == counts
    orders = re.search(r"INSERT INTO retail_orders VALUES(.*?);", seed, re.S).group(1)
    assert len(re.findall(r"\('O\d+'", orders)) == 12
    with (ROOT / "demo/enterprise_retail/knowledge_base.csv").open(encoding="utf-8") as handle:
        docs = {row["doc_id"]: row["content"] for row in csv.DictReader(handle)}
    assert "7 calendar days" in docs["ENT-REFUND-001"]
    assert "1 business day" in docs["ENT-SOP-001"]


def test_operator_model_labels_are_metadata_only(monkeypatch):
    monkeypatch.setattr("eval.run_eval._git_output", lambda *args: "" if args[0] == "status" else "test-commit")
    metadata = collect_environment_metadata(
        dataset_path=ROOT / "eval/datasets/enterprise_retail_natural_v1.jsonl",
        base_url="http://localhost:8000", timeout=600, retry_count=0, case_count=6,
        model_label="example-model", provider_label="example-provider",
    )
    assert metadata["model_label"] == "example-model"
    assert metadata["provider_label"] == "example-provider"
    assert metadata["git_dirty"] is False
    assert len(metadata["dataset_sha256"]) == 64
