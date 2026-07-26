#!/usr/bin/env python3
"""Run an IFEval subset through Ollama and score it with Google's evaluator."""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_SOURCE = Path(
    "eval-data/google-research/instruction_following_eval/data/input_data.jsonl"
)
GOOGLE_RESEARCH_ROOT = Path("eval-data/google-research")
NLTK_DATA_ROOT = Path("eval-data/nltk_data")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def query(
    url: str, model: str, prompt: str, max_tokens: int
) -> tuple[dict[str, Any], float]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
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
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def score(
    inputs_path: Path, responses_path: Path, output_dir: Path
) -> dict[str, Any]:
    sys.path.insert(0, str(GOOGLE_RESEARCH_ROOT.resolve()))
    if NLTK_DATA_ROOT.exists():
        import nltk

        nltk.data.path.insert(0, str(NLTK_DATA_ROOT.resolve()))
    from instruction_following_eval import evaluation_lib

    inputs = evaluation_lib.read_prompt_list(str(inputs_path))
    prompt_to_response = evaluation_lib.read_prompt_to_response_dict(
        str(responses_path)
    )
    summary: dict[str, Any] = {}
    for mode, evaluator in [
        ("strict", evaluation_lib.test_instruction_following_strict),
        ("loose", evaluation_lib.test_instruction_following_loose),
    ]:
        outputs = [evaluator(item, prompt_to_response) for item in inputs]
        output_path = output_dir / f"eval_results_{mode}.jsonl"
        evaluation_lib.write_outputs(str(output_path), outputs)
        prompt_passes = sum(item.follow_all_instructions for item in outputs)
        instruction_total = sum(
            len(item.follow_instruction_list) for item in outputs
        )
        instruction_passes = sum(
            sum(item.follow_instruction_list) for item in outputs
        )
        summary[mode] = {
            "prompt_correct": prompt_passes,
            "prompt_total": len(outputs),
            "prompt_accuracy": prompt_passes / len(outputs),
            "instruction_correct": instruction_passes,
            "instruction_total": instruction_total,
            "instruction_accuracy": instruction_passes / instruction_total,
            "results": str(output_path),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--label")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--input-data", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()

    selected = read_jsonl(args.input_data)[: args.limit]
    label = args.label or args.model.replace(":", "-").replace("/", "-")
    output_dir = Path("eval-results/ifeval") / f"{label}-{args.limit}"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_path = output_dir / "input_data.jsonl"
    responses_path = output_dir / "responses.jsonl"

    with inputs_path.open("w", encoding="utf-8") as output:
        for item in selected:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")

    records = read_jsonl(responses_path) if responses_path.exists() else []
    complete_cache = len(records) == len(selected) and all(
        record.get("key") == item["key"]
        and record.get("prompt") == item["prompt"]
        for record, item in zip(records, selected)
    )
    if complete_cache:
        truncated_indexes = [
            index
            for index, record in enumerate(records)
            if record.get("done_reason") == "length"
            and record.get("output_tokens", 0) < args.max_tokens
        ]
        if truncated_indexes:
            print(
                f"Reusing cache and retrying {len(truncated_indexes)} "
                "previously truncated response(s)"
            )
            for index in truncated_indexes:
                item = selected[index]
                result, elapsed = query(
                    args.url, args.model, item["prompt"], args.max_tokens
                )
                records[index] = {
                    "key": item["key"],
                    "prompt": item["prompt"],
                    "response": result.get("message", {}).get("content", ""),
                    "elapsed_seconds": round(elapsed, 3),
                    "output_tokens": result.get("eval_count", 0),
                    "done_reason": result.get("done_reason"),
                }
            with responses_path.open("w", encoding="utf-8") as output:
                for record in records:
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
        else:
            print(
                f"Reusing {len(records)} cached responses from {responses_path}"
            )
    else:
        records = []
        with responses_path.open("w", encoding="utf-8") as output:
            for index, item in enumerate(selected, 1):
                result, elapsed = query(
                    args.url, args.model, item["prompt"], args.max_tokens
                )
                message = result.get("message", {})
                done_reason = result.get("done_reason")
                record = {
                    "key": item["key"],
                    "prompt": item["prompt"],
                    "response": message.get("content", ""),
                    "elapsed_seconds": round(elapsed, 3),
                    "output_tokens": result.get("eval_count", 0),
                    "done_reason": done_reason,
                }
                records.append(record)
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
                print(
                    f"{index}/{args.limit} key={item['key']} "
                    f"time={elapsed:.2f}s "
                    f"tokens={result.get('eval_count', 0)} "
                    f"done={done_reason}"
                )

    elapsed_total = sum(item["elapsed_seconds"] for item in records)
    output_tokens = sum(item["output_tokens"] for item in records)
    truncated = sum(item["done_reason"] == "length" for item in records)

    summary = {
        "model": args.model,
        "dataset": "IFEval fixed leading subset",
        "samples": len(selected),
        "think": False,
        "temperature": 0,
        "num_ctx": 4096,
        "max_tokens": args.max_tokens,
        "average_seconds": elapsed_total / len(selected),
        "average_output_tokens": output_tokens / len(selected),
        "truncated": truncated,
        "scores": score(inputs_path, responses_path, output_dir),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
