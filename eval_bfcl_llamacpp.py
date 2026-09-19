#!/usr/bin/env python3
"""Run fixed BFCL v4 category samples through llama.cpp's OpenAI-compatible API.

Scoring is imported from eval_bfcl_ollama.py rather than reimplemented, so the
subset and the grading stay identical between engines -- only the transport
differs.  Same caveat as the Ollama runner: this is a compact local diagnostic,
not an official BFCL leaderboard runner.
"""

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from eval_bfcl_ollama import (
    CATEGORIES,
    DEFAULT_DATA_ROOT,
    expected_multi_turn,
    multi_turn_functions,
    normalize_schema,
    read_jsonl,
    score_calls,
)


def fix_schema_types(node: Any) -> Any:
    """llama.cpp validates tool schemas strictly and rejects type "float",
    which is not a valid JSON Schema type -- the BFCL function docs contain a
    few of them and Ollama tolerated it. Without this, affected items fail with
    HTTP 500 ("JSON schema error ... unrecognized type float") before the model
    is ever asked, i.e. they are unscoreable by construction rather than failed.
    """
    if isinstance(node, dict):
        return {key: ("number" if key == "type" and value == "float"
                      else fix_schema_types(value))
                for key, value in node.items()}
    if isinstance(node, list):
        return [fix_schema_types(item) for item in node]
    return node


def tool_schema(function: dict[str, Any]) -> dict[str, Any]:
    return fix_schema_types(normalize_schema(function))


def query(url: str, api_key: str, messages: list[dict[str, Any]],
          functions: list[dict[str, Any]], max_tokens: int) -> tuple[dict[str, Any], float]:
    payload = {"messages": messages,
               "tools": [tool_schema(f) for f in functions],
               "temperature": 0, "max_tokens": max_tokens}
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def run_test(args: argparse.Namespace, test: dict[str, Any], ground_truth: Any,
             functions: list[dict[str, Any]]) -> dict[str, Any]:
    elapsed_total, tokens, turns, messages = 0.0, 0, [], []
    question_turns = test["question"]
    expected_turns = ground_truth if args.category == "multi_turn_base" else [ground_truth]
    if args.category != "multi_turn_base":
        question_turns = [question_turns[0]]
    all_ok = True
    for turn_index, user_messages in enumerate(question_turns):
        messages.extend(user_messages)
        expected = (expected_multi_turn(expected_turns[turn_index], functions)
                    if args.category == "multi_turn_base" else expected_turns[turn_index])
        result, elapsed = query(args.url, args.api_key, messages, functions, args.max_tokens)
        choice = result["choices"][0]
        message = choice.get("message", {})
        calls = message.get("tool_calls") or []
        content = message.get("content") or ""
        ok, reason = score_calls(calls, expected)
        all_ok &= ok
        elapsed_total += elapsed
        tokens += result.get("usage", {}).get("completion_tokens", 0)
        turns.append({"turn": turn_index + 1, "expected": expected, "tool_calls": calls,
                      "passed": ok, "reason": reason, "content": content})
        # Preserve context without executing benchmark-side effects.
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for call in calls:
            entry = {"role": "tool", "content": json.dumps({"status": "success"})}
            if call.get("id"):
                entry["tool_call_id"] = call["id"]
            messages.append(entry)
    return {"passed": all_ok, "reason": "pass" if all_ok else "one_or_more_turns_failed",
            "turns": turns, "elapsed_seconds": round(elapsed_total, 3), "output_tokens": tokens,
            "finish_reason": result["choices"][0].get("finish_reason")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--category", choices=CATEGORIES, default="simple_python")
    parser.add_argument("--label", default="ornith-1.5-9b-obliterated")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--engine", default="llama.cpp")
    args = parser.parse_args()

    tests = read_jsonl(args.data_root / f"BFCL_v4_{args.category}.json")
    if args.category == "irrelevance":
        answers = {test["id"]: [] for test in tests}
    else:
        answers = {item["id"]: item["ground_truth"] for item in
                   read_jsonl(args.data_root / "possible_answer" / f"BFCL_v4_{args.category}.json")}
    selected = tests[args.offset:args.offset + args.limit]
    output_dir = Path("eval-results/tool-calling")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (f"bfcl-v4-{args.category.replace('_', '-')}-{args.label}"
                                f"-n{len(selected)}-o{args.offset}.jsonl")

    passed = elapsed_total = output_tokens = 0
    with output_path.open("w", encoding="utf-8") as output:
        for index, test in enumerate(selected, 1):
            functions = (multi_turn_functions(test, args.data_root)
                         if args.category == "multi_turn_base" else test["function"])
            try:
                record = run_test(args, test, answers[test["id"]], functions)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
                record = {"passed": False, "reason": "api_error", "turns": [],
                          "elapsed_seconds": 0, "output_tokens": 0, "error": str(exc)}
            record.update({"index": index, "id": test["id"], "category": args.category,
                           "engine": args.engine})
            passed += int(record["passed"])
            elapsed_total += record["elapsed_seconds"]
            output_tokens += record["output_tokens"]
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(f"{index}/{len(selected)} {'PASS' if record['passed'] else 'FAIL'} "
                  f"{test['id']} reason={record['reason']} time={record['elapsed_seconds']:.2f}s")
    total = len(selected)
    print(json.dumps({"model": args.label, "engine": args.engine, "category": args.category,
                      "sample": f"offset={args.offset},limit={args.limit}",
                      "correct": passed, "total": total, "accuracy": passed / total,
                      "average_seconds": elapsed_total / total,
                      "average_output_tokens": output_tokens / total,
                      "results": str(output_path), "official_leaderboard_score": False},
                     indent=2))


if __name__ == "__main__":
    main()
