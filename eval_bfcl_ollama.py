#!/usr/bin/env python3
"""Run fixed BFCL v4 category samples through Ollama's native tools API.

This is a compact local diagnostic, not an official BFCL leaderboard runner.
Single-turn calls are scored as unordered exact call sets.  Multi-turn cases are
scored turn-by-turn against BFCL's call sequences, using synthetic successful
tool responses so every model sees the same deterministic conversation.
"""

import argparse
import ast
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_DATA_ROOT = Path("eval-data/gorilla/berkeley-function-call-leaderboard/bfcl_eval/data")
CATEGORIES = ("simple_python", "multiple", "parallel", "parallel_multiple", "irrelevance", "multi_turn_base")
FUNC_DOC_FILES = {
    "GorillaFileSystem": "gorilla_file_system.json", "MathAPI": "math_api.json",
    "MessageAPI": "message_api.json", "TwitterAPI": "posting_api.json",
    "TicketAPI": "ticket_api.json", "TradingBot": "trading_bot.json",
    "TravelAPI": "travel_booking.json", "VehicleControlAPI": "vehicle_control.json",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def normalize_schema(function: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(function))
    parameters = normalized.get("parameters", {})
    if parameters.get("type") == "dict":
        parameters["type"] = "object"
    return {"type": "function", "function": normalized}


def query(url: str, model: str, messages: list[dict[str, Any]],
          functions: list[dict[str, Any]], max_tokens: int) -> tuple[dict[str, Any], float]:
    payload = {"model": model, "messages": messages,
               "tools": [normalize_schema(f) for f in functions], "stream": False,
               "think": False, "options": {"temperature": 0, "num_ctx": 4096,
                                            "num_predict": max_tokens}}
    request = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=600) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def parse_call(call: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    function = call.get("function", {})
    arguments = function.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return function.get("name"), None
    return function.get("name"), arguments if isinstance(arguments, dict) else None


def value_matches(actual: Any, allowed: list[Any]) -> bool:
    return any(actual == expected or
               (isinstance(actual, (int, float)) and isinstance(expected, (int, float))
                and float(actual) == float(expected)) or
               str(actual).lower() == str(expected).lower() for expected in allowed)


def call_matches(call: dict[str, Any], expected: dict[str, Any]) -> bool:
    name, args = parse_call(call)
    if args is None or len(expected) != 1:
        return False
    expected_name, expected_args = next(iter(expected.items()))
    if name != expected_name:
        return False
    required = {key for key, allowed in expected_args.items() if "" not in allowed and None not in allowed}
    return (required.issubset(args) and set(args).issubset(expected_args) and
            all(value_matches(value, expected_args[key]) for key, value in args.items()))


def score_calls(calls: list[dict[str, Any]], expected: list[dict[str, Any]]) -> tuple[bool, str]:
    if len(calls) != len(expected):
        return False, f"expected_{len(expected)}_calls_got_{len(calls)}"
    remaining = list(expected)
    for call in calls:
        match = next((i for i, item in enumerate(remaining) if call_matches(call, item)), None)
        if match is None:
            return False, "wrong_call"
        remaining.pop(match)
    return True, "pass"


def parse_ground_truth_call(text: str) -> dict[str, Any]:
    node = ast.parse(text, mode="eval").body
    if not isinstance(node, ast.Call):
        raise ValueError(text)
    name = node.func.id if isinstance(node.func, ast.Name) else ast.unparse(node.func)
    args = {kw.arg: ast.literal_eval(kw.value) for kw in node.keywords}
    doc = {name: {key: [value] for key, value in args.items()}}
    # A few BFCL answers use positional arguments; map them later by schema order.
    doc[name]["__positional__"] = [ast.literal_eval(arg) for arg in node.args]
    return doc


def multi_turn_functions(test: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for class_name in test["involved_classes"]:
        docs.extend(read_jsonl(root / "multi_turn_func_doc" / FUNC_DOC_FILES[class_name]))
    excluded = set(test.get("excluded_function", []))
    return [doc for doc in docs if doc["name"] not in excluded]


def expected_multi_turn(turn: list[str], functions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schemas = {f["name"]: f for f in functions}
    expected = []
    for text in turn:
        item = parse_ground_truth_call(text)
        name, args = next(iter(item.items()))
        positional = args.pop("__positional__")
        keys = list(schemas[name].get("parameters", {}).get("properties", {}))
        for key, value in zip(keys, positional):
            args[key] = [value]
        expected.append(item)
    return expected


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
        result, elapsed = query(args.url, args.model, messages, functions, args.max_tokens)
        calls = result.get("message", {}).get("tool_calls") or []
        ok, reason = score_calls(calls, expected)
        all_ok &= ok
        elapsed_total += elapsed
        tokens += result.get("eval_count", 0)
        turns.append({"turn": turn_index + 1, "expected": expected, "tool_calls": calls,
                      "passed": ok, "reason": reason, "content": result.get("message", {}).get("content", "")})
        # Preserve context without executing benchmark-side effects.
        messages.append(result.get("message", {"role": "assistant", "content": ""}))
        for call in calls:
            messages.append({"role": "tool", "content": json.dumps({"status": "success"})})
    return {"passed": all_ok, "reason": "pass" if all_ok else "one_or_more_turns_failed",
            "turns": turns, "elapsed_seconds": round(elapsed_total, 3), "output_tokens": tokens}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--category", choices=CATEGORIES, default="simple_python")
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--label")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()

    tests = read_jsonl(args.data_root / f"BFCL_v4_{args.category}.json")
    if args.category == "irrelevance":
        answers = {test["id"]: [] for test in tests}
    else:
        answers = {item["id"]: item["ground_truth"] for item in
                   read_jsonl(args.data_root / "possible_answer" / f"BFCL_v4_{args.category}.json")}
    selected = tests[args.offset:args.offset + args.limit]
    label = args.label or args.model.replace(":", "-").replace("/", "-")
    output_dir = Path("eval-results/tool-calling")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"bfcl-v4-{args.category.replace('_', '-')}-{label}-n{len(selected)}-o{args.offset}.jsonl"

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
            record.update({"index": index, "id": test["id"], "category": args.category})
            passed += int(record["passed"])
            elapsed_total += record["elapsed_seconds"]
            output_tokens += record["output_tokens"]
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(f"{index}/{len(selected)} {'PASS' if record['passed'] else 'FAIL'} "
                  f"{test['id']} reason={record['reason']} time={record['elapsed_seconds']:.2f}s")
    total = len(selected)
    print(json.dumps({"model": args.model, "category": args.category, "sample": f"offset={args.offset},limit={args.limit}",
                      "correct": passed, "total": total, "accuracy": passed / total,
                      "average_seconds": elapsed_total / total, "average_output_tokens": output_tokens / total,
                      "results": str(output_path), "official_leaderboard_score": False}, indent=2))


if __name__ == "__main__":
    main()
