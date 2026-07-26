#!/usr/bin/env python3
"""Small, practical GSM8K runner for Ollama's native think switch."""

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

from datasets import load_from_disk


def find_test_dataset() -> Path:
    candidates = sorted(Path("eval-data/datasets").glob("AI-ModelScope_gsm8k-*"))
    for path in candidates:
        dataset = load_from_disk(str(path))
        if len(dataset) == 1319:
            return path
    raise FileNotFoundError("GSM8K test dataset was not found under eval-data/datasets")


def extract_number(text: str) -> str | None:
    boxed = re.findall(r"\\boxed\{([^{}]+)\}", text)
    if boxed:
        text = boxed[-1]
    numbers = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    return numbers[-1].replace(",", "") if numbers else None


def query(
    prompt: str, model: str, url: str, think: bool, max_tokens: int
) -> tuple[dict, float]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": think,
        "options": {
            "temperature": 0,
            "num_predict": max_tokens,
            "num_ctx": 4096,
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--model", default="nanbeige4.2:3b-q6")
    parser.add_argument("--url", default="http://127.0.0.1:11435/api/chat")
    parser.add_argument("--label", default=None)
    parser.add_argument("--think", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    dataset = load_from_disk(str(find_test_dataset()))
    output_dir = Path("eval-results/custom")
    output_dir.mkdir(parents=True, exist_ok=True)
    mode = "think" if args.think else "no-think"
    label = args.label or re.sub(r"[^a-zA-Z0-9._-]+", "-", args.model)
    output_path = output_dir / f"gsm8k-{label}-{mode}-{args.limit}.jsonl"

    correct = 0
    elapsed_total = 0.0
    output_tokens = 0
    with output_path.open("w", encoding="utf-8") as output:
        for index, sample in enumerate(dataset.select(range(args.limit))):
            prompt = (
                f"{sample['question']}\n"
                "请计算并只输出最终答案，格式必须是：\\boxed{数字}"
            )
            result, elapsed = query(
                prompt, args.model, args.url, args.think, args.max_tokens
            )
            content = result.get("message", {}).get("content", "")
            reasoning = result.get("message", {}).get("thinking", "")
            prediction = extract_number(content)
            target = sample["answer"].rsplit("####", 1)[-1].strip().replace(",", "")
            passed = prediction == target
            correct += int(passed)
            elapsed_total += elapsed
            output_tokens += result.get("eval_count", 0)
            record = {
                "index": index,
                "question": sample["question"],
                "target": target,
                "prediction": prediction,
                "passed": passed,
                "elapsed_seconds": round(elapsed, 3),
                "output_tokens": result.get("eval_count"),
                "content": content,
                "reasoning": reasoning,
                "done_reason": result.get("done_reason"),
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(
                f"{index + 1}/{args.limit} "
                f"{'PASS' if passed else 'FAIL'} "
                f"target={target} prediction={prediction} "
                f"time={elapsed:.2f}s tokens={result.get('eval_count', 0)}"
            )

    print(
        json.dumps(
            {
                "mode": mode,
                "model": args.model,
                "correct": correct,
                "total": args.limit,
                "accuracy": correct / args.limit,
                "average_seconds": elapsed_total / args.limit,
                "average_output_tokens": output_tokens / args.limit,
                "results": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
