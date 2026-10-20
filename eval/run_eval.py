import argparse
import datetime as dt
import hashlib
import json
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# Running ``python eval/run_eval.py`` makes ``eval/`` sys.path[0]. Add the
# repository root explicitly so project imports such as ``gustobot`` resolve
# without requiring callers to set PYTHONPATH manually.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluators import evaluate_case, summarize_results


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "enterprise_retail_v1.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GustoBot end-to-end evaluation cases.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="Path to JSONL evaluation cases.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL.")
    parser.add_argument("--output-dir", default=str(Path(__file__).parent / "results"))
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--user-id", default="eval_runner")
    parser.add_argument("--case-id", action="append", help="Run only matching case id. Can be repeated.")
    parser.add_argument("--wait-ready-timeout", type=float, default=120.0, help="Seconds to wait for backend readiness before running cases.")
    parser.add_argument("--retry-count", type=int, default=0, help="Retries per case for transient transport failures. Core baseline defaults to 0 so failures remain visible.")
    parser.add_argument("--retry-backoff", type=float, default=2.0, help="Seconds to wait between retries.")
    parser.add_argument("--min-route-accuracy", type=float, default=None)
    parser.add_argument("--max-p95-latency-ms", type=float, default=None)
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    cases = load_cases(dataset_path, args.case_id or [])
    if not cases:
        print(f"No cases found in {dataset_path}", file=sys.stderr)
        return 2

    if not wait_for_backend_ready(args.base_url, args.wait_ready_timeout):
        print(
            f"Backend is not ready after {args.wait_ready_timeout:.0f}s: {args.base_url}",
            file=sys.stderr,
        )
        return 2

    # Capture reproducibility metadata before creating result artifacts so
    # generated output files cannot make a clean baseline look dirty.
    environment_metadata = collect_environment_metadata(
        dataset_path=dataset_path,
        base_url=args.base_url,
        timeout=args.timeout,
        retry_count=args.retry_count,
        case_count=len(cases),
    )

    run_dir = Path(args.output_dir) / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        case_id = case.get("id", f"case_{index}")
        print(f"[{index}/{len(cases)}] {case_id}: {case.get('query')}")
        response, latency_ms, error, latency_attempts, http_status = call_chat_api_with_retries(
            base_url=args.base_url,
            query=case["query"],
            user_id=f"{args.user_id}_{case_id}",
            trace_id=f"eval-{case_id}-{uuid.uuid4().hex[:8]}",
            timeout=args.timeout,
            retry_count=args.retry_count,
            retry_backoff=args.retry_backoff,
            file_path=case.get("file_path"),
            ingest_incremental=case.get("ingest_incremental"),
        )
        result = evaluate_case(
            case=case,
            response=response,
            latency_ms=latency_ms,
            error=error,
            latency_attempts=latency_attempts,
            http_status=http_status,
        )
        result["response_tool_results"] = extract_response_tool_results(response)
        results.append(result)
        print_case_status(result)

    summary = summarize_results(results)
    write_jsonl(run_dir / "cases.jsonl", results)
    write_json(run_dir / "summary.json", summary)
    write_json(run_dir / "environment.json", environment_metadata)
    write_report(run_dir / "report.md", summary, results, dataset_path)

    print("")
    print(f"Report written to: {run_dir / 'report.md'}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not thresholds_passed(summary, args):
        return 1
    return 0


def load_cases(dataset_path: Path, selected_ids: Sequence[str]) -> List[Dict[str, Any]]:
    selected = set(selected_ids)
    cases: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            case = json.loads(stripped)
            if case.get("enabled", True) is False:
                continue
            if selected and case.get("id") not in selected:
                continue
            if "query" not in case:
                raise ValueError(f"Case at line {line_number} is missing query")
            cases.append(case)
    return cases


def wait_for_backend_ready(base_url: str, timeout_seconds: float) -> bool:
    deadline = time.perf_counter() + timeout_seconds
    url = base_url.rstrip("/") + "/api/v1/chat/routes"
    last_error = ""
    while time.perf_counter() < deadline:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=5) as response:
                if 200 <= response.status < 500:
                    print(f"Backend ready: {url}")
                    return True
        except Exception as exc:
            last_error = repr(exc)
        time.sleep(2)
    if last_error:
        print(f"Last readiness error: {last_error}", file=sys.stderr)
    return False


def call_chat_api_with_retries(
    base_url: str,
    query: str,
    user_id: str,
    trace_id: str,
    timeout: float,
    retry_count: int,
    retry_backoff: float,
    file_path: Optional[str] = None,
    ingest_incremental: Optional[bool] = None,
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str], List[Dict[str, Any]], Optional[int]]:
    total_latency_ms = 0.0
    last_response: Optional[Dict[str, Any]] = None
    last_error: Optional[str] = None
    last_http_status: Optional[int] = None
    attempts: List[Dict[str, Any]] = []
    for attempt in range(retry_count + 1):
        response, latency_ms, error, http_status = call_chat_api(
            base_url=base_url,
            query=query,
            user_id=user_id,
            trace_id=trace_id,
            timeout=timeout,
            file_path=file_path,
            ingest_incremental=ingest_incremental,
        )
        total_latency_ms += latency_ms
        last_response = response
        last_error = error
        last_http_status = http_status
        attempts.append(
            {
                "attempt": attempt + 1,
                "latency_ms": round(latency_ms, 2),
                "success": error is None,
                "error": error,
                "http_status": http_status,
            }
        )
        if error is None:
            return response, total_latency_ms, None, attempts, http_status
        if attempt < retry_count and is_transient_error(error, http_status):
            print(f"  transient error, retrying in {retry_backoff:.1f}s: {error}")
            time.sleep(retry_backoff)
            continue
        break
    return last_response, total_latency_ms, last_error, attempts, last_http_status


def is_transient_error(error: str, http_status: Optional[int] = None) -> bool:
    if http_status in {429, 502, 503}:
        return True
    markers = (
        "RemoteDisconnected",
        "ConnectionAbortedError",
        "ConnectionResetError",
        "ConnectionRefusedError",
        "timed out",
        "TimeoutError",
    )
    return any(marker in error for marker in markers)


def call_chat_api(
    base_url: str,
    query: str,
    user_id: str,
    trace_id: str,
    timeout: float,
    file_path: Optional[str] = None,
    ingest_incremental: Optional[bool] = None,
) -> Tuple[Optional[Dict[str, Any]], float, Optional[str], Optional[int]]:
    url = base_url.rstrip("/") + "/api/v1/chat/"
    payload = {"message": query, "user_id": user_id, "stream": False, "trace_id": trace_id}
    if file_path:
        payload["file_path"] = file_path
    if isinstance(ingest_incremental, bool):
        payload["ingest_incremental"] = ingest_incremental
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    started_at = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            latency_ms = (time.perf_counter() - started_at) * 1000
            return json.loads(raw), latency_ms, None, response.status
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        body = exc.read().decode("utf-8", errors="replace")
        return None, latency_ms, f"HTTP {exc.code}: {body[:500]}", exc.code
    except Exception as exc:
        latency_ms = (time.perf_counter() - started_at) * 1000
        return None, latency_ms, repr(exc), None


def print_case_status(result: Dict[str, Any]) -> None:
    metrics = result["metrics"]
    print(
        "  http={http} route={actual}/{expected} route_ok={route_ok} exec={execution_status} "
        "tools={tools} evidence={evidence} fallback={fallback} latency={latency}ms".format(
            http=result["actual"].get("http_status"),
            actual=result["actual"].get("route"),
            expected=result["expected"].get("route"),
            route_ok=metric_status(metrics.get("route_correct")),
            execution_status=result["actual"].get("execution_status"),
            tools=",".join(result["actual"].get("executed_tools") or []),
            evidence=result["actual"].get("evidence_count"),
            fallback=result.get("fallback_reason"),
            latency=result.get("latency_ms"),
        )
    )
    if result.get("error"):
        print(f"  error={result['error']}")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + "\n", encoding="utf-8")


def extract_response_tool_results(response: Optional[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
    """Best-effort extraction of serialized tool results from a chat response."""
    if not isinstance(response, dict):
        return None

    found: List[Dict[str, Any]] = []
    seen = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            candidates = value.get("tool_results")
            if isinstance(candidates, dict):
                candidates = [candidates]
            if isinstance(candidates, list):
                for item in candidates:
                    if isinstance(item, dict):
                        marker = repr(sorted((key, repr(val)) for key, val in item.items()))
                        if marker not in seen:
                            seen.add(marker)
                            found.append(item)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(response)
    return found or None


def collect_environment_metadata(
    *, dataset_path: Path, base_url: str, timeout: float, retry_count: int, case_count: int
) -> Dict[str, Any]:
    dataset_bytes = dataset_path.read_bytes()
    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "commit_hash": _git_output("rev-parse", "HEAD"),
        "git_dirty": bool(_git_output("status", "--porcelain")),
        "dataset_path": str(dataset_path),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "case_count": case_count,
        "base_url": base_url,
        "request_timeout_seconds": timeout,
        "runner_retry_count": retry_count,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }


def _git_output(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def write_report(
    path: Path,
    summary: Dict[str, Any],
    results: Sequence[Dict[str, Any]],
    dataset_path: Path,
) -> None:
    formal_metrics = (
        "http_success_rate",
        "agent_completion_rate",
        "route_accuracy",
        "tool_selection_accuracy",
        "tool_execution_success_rate",
        "evidence_available_accuracy",
        "expected_fact_supported_by_evidence_rate",
        "avg_total_latency_ms",
        "p95_total_latency_ms",
    )
    diagnostic_metrics = (
        "execution_status_counts",
        "tool_status_counts",
        "fallback_reason_counts",
        "fallback_rate",
        "partial_success_rate",
        "transport_error_rate",
        "evidence_available_rate",
        "avg_retry_count",
        "avg_latency_ms_router",
        "avg_latency_ms_planner",
        "avg_latency_ms_tool",
        "avg_observed_duration_ms_tool",
        "avg_completed_latency_ms_tool",
        "avg_latency_ms_answer",
    )
    lines = [
        "# GustoBot Core Evaluation Report",
        "",
        f"- Dataset: `{dataset_path}`",
        f"- Generated at: `{dt.datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Formal Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in formal_metrics:
        lines.append(f"| `{key}` | {format_metric(summary.get(key))} |")
    lines.extend(["", "## Diagnostics", "", "| Metric | Value |", "| --- | ---: |"])
    for key in diagnostic_metrics:
        lines.append(f"| `{key}` | {md_escape(summary.get(key))} |")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | HTTP | Route | Route OK | Tools | Execution | Evidence | Fact Support | Fallback | Latency ms | Error |",
            "| --- | ---: | --- | ---: | --- | --- | ---: | ---: | --- | ---: | --- |",
        ]
    )
    for result in results:
        metrics = result["metrics"]
        route = "{}/{}".format(result["actual"].get("route"), result["expected"].get("route"))
        lines.append(
            "| {case_id} | {http} | {route} | {route_ok} | {tools} | {execution} | {evidence} | {fact_support} | {fallback} | {latency} | {error} |".format(
                case_id=md_escape(result.get("id")),
                http=format_metric(result["actual"].get("http_status")),
                route=md_escape(route),
                route_ok=format_metric(metrics.get("route_correct")),
                tools=md_escape(", ".join(result["actual"].get("executed_tools") or [])),
                execution=md_escape(result["actual"].get("execution_status") or ""),
                evidence=format_metric(result["actual"].get("evidence_count")),
                fact_support=format_metric(metrics.get("expected_fact_supported_by_evidence")),
                fallback=md_escape(result.get("fallback_reason") or "none"),
                latency=format_metric(result.get("latency_ms")),
                error=md_escape(result.get("error") or ""),
            )
        )
    lines.extend(
        [
            "",
            "## Metric Semantics",
            "",
            "- `expected_fact_supported_by_evidence` is deterministic expected-fact support in canonical Evidence content; it is not grounded faithfulness.",
            "- `fallback_reason` reports only real alternate-strategy fallback. Empty/error/transport outcomes are reported separately.",
            "- Latency is observational in Phase E. Do not set reliability timeouts from a single run; use the three-run baseline first.",
            "- `null` metrics are excluded from aggregate denominators rather than silently counted as success.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")

def thresholds_passed(summary: Dict[str, Any], args: argparse.Namespace) -> bool:
    ok = True
    if args.min_route_accuracy is not None:
        actual = summary.get("route_accuracy")
        if actual is None or actual < args.min_route_accuracy:
            print(
                f"Threshold failed: route_accuracy={actual} < {args.min_route_accuracy}",
                file=sys.stderr,
            )
            ok = False
    if args.max_p95_latency_ms is not None:
        actual = summary.get("p95_latency_ms")
        if actual is None or actual > args.max_p95_latency_ms:
            print(
                f"Threshold failed: p95_latency_ms={actual} > {args.max_p95_latency_ms}",
                file=sys.stderr,
            )
            ok = False
    return ok


def metric_status(value: Optional[Any]) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "pass" if value else "fail"
    return str(value)


def format_metric(value: Optional[Any]) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.4f}" if value <= 1 else f"{value:.2f}"
    return str(value)


def md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
