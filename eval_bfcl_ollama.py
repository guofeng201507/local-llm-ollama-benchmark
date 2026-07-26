#!/usr/bin/env python3
"""Run a small BFCL v4 simple_python subset through Ollama's native tools API."""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_DATA_ROOT = Path(
    "eval-data/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalize_schema(function: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(function))
    parameters = normalized.get("parameters", {})
    if parameters.get("type") == "dict":
        parameters["type"] = "object"
    return {"type": "function", "function": normalized}


def query(
    url: str,
    model: str,
    messages: list[dict[str, Any]],
    functions: list[dict[str, Any]],
    max_tokens: int,
) -> tuple[dict[str, Any], float]:
    payload = {
        "model": model,
        "messages": messages,
        "tools": [normalize_schema(function) for function in functions],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_ctx": 4096,
            "num_predict": max_tokens,
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def value_matches(actual: Any, allowed: list[Any]) -> bool:
    for expected in allowed:
        if actual == expected:
            return True
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            if float(actual) == float(expected):
                return True
        if str(actual).lower() == str(expected).lower():
            return True
    return False


def score_call(
    tool_calls: list[dict[str, Any]], possible_answers: list[dict[str, Any]]
) -> tuple[bool, str]:
    if len(tool_calls) != 1:
        return False, f"expected_one_call_got_{len(tool_calls)}"

    function = tool_calls[0].get("function", {})
    actual_name = function.get("name")
    actual_args = function.get("arguments", {})
    if isinstance(actual_args, str):
        try:
            actual_args = json.loads(actual_args)
        except json.JSONDecodeError:
            return False, "arguments_not_json"
    if not isinstance(actual_args, dict):
        return False, "arguments_not_object"

    for possible in possible_answers:
        if len(possible) != 1:
            continue
        expected_name, expected_args = next(iter(possible.items()))
        if actual_name != expected_name:
            continue

        required_keys = {
            key
            for key, allowed in expected_args.items()
            if "" not in allowed and None not in allowed
        }
        if not required_keys.issubset(actual_args):
            return False, "missing_required_argument"
        if not set(actual_args).issubset(expected_args):
            return False, "unexpected_argument"

        for key, actual_value in actual_args.items():
            if not value_matches(actual_value, expected_args[key]):
                return False, f"wrong_argument_{key}"
        return True, "pass"

    return False, "wrong_function"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--label")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()

    tests = read_jsonl(args.data_root / "BFCL_v4_simple_python.json")
    answers = {
        item["id"]: item["ground_truth"]
        for item in read_jsonl(
            args.data_root / "possible_answer/BFCL_v4_simple_python.json"
        )
    }
    selected = tests[: args.limit]
    label = args.label or args.model.replace(":", "-").replace("/", "-")
    output_dir = Path("eval-results/tool-calling")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"bfcl-v4-simple-python-{label}-{args.limit}.jsonl"

    passed = 0
    elapsed_total = 0.0
    output_tokens = 0
    with output_path.open("w", encoding="utf-8") as output:
        for index, test in enumerate(selected, 1):
            messages = test["question"][0]
            error = None
            result: dict[str, Any] = {}
            elapsed = 0.0
            try:
                result, elapsed = query(
                    args.url,
                    args.model,
                    messages,
                    test["function"],
                    args.max_tokens,
                )
                tool_calls = result.get("message", {}).get("tool_calls") or []
                ok, reason = score_call(tool_calls, answers[test["id"]])
            except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                ok = False
                reason = "api_error"
                error = str(exc)
                tool_calls = []

            passed += int(ok)
            elapsed_total += elapsed
            output_tokens += result.get("eval_count", 0)
            record = {
                "index": index,
                "id": test["id"],
                "question": messages,
                "functions": test["function"],
                "ground_truth": answers[test["id"]],
                "tool_calls": tool_calls,
                "passed": ok,
                "reason": reason,
                "elapsed_seconds": round(elapsed, 3),
                "output_tokens": result.get("eval_count", 0),
                "content": result.get("message", {}).get("content", ""),
                "error": error,
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(
                f"{index}/{args.limit} {'PASS' if ok else 'FAIL'} "
                f"{test['id']} reason={reason} time={elapsed:.2f}s"
            )

    total = len(selected)
    print(
        json.dumps(
            {
                "model": args.model,
                "dataset": "BFCL v4 simple_python leading subset",
                "correct": passed,
                "total": total,
                "accuracy": passed / total,
                "average_seconds": elapsed_total / total,
                "average_output_tokens": output_tokens / total,
                "results": str(output_path),
                "official_leaderboard_score": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
