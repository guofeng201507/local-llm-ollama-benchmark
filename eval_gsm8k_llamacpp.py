#!/usr/bin/env python3
"""GSM8K runner for llama.cpp's OpenAI-compatible server.

Deliberately mirrors eval_gsm8k_ollama.py -- same prompt, same answer
extraction, same metrics (accuracy, average seconds, average output tokens) --
so that results from a llama.cpp machine can sit next to the Ollama results.

One structural difference: llama.cpp has no per-request think switch. Thinking
is fixed by the server's --reasoning flag, and the thoughts come back in
message.reasoning_content (Ollama uses message.thinking). So run this twice
against two server configurations to fill in the normal/thinking columns.

The dataset is fetched from the official openai/grade-school-math URL unless
--jsonl points at a local copy, so no HF cache is required.
"""

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path

GSM8K_URL = ("https://raw.githubusercontent.com/openai/grade-school-math/"
             "master/grade_school_math/data/test.jsonl")

PROMPT_SUFFIX = "\n请计算并只输出最终答案，格式必须是：\\boxed{数字}"


def load_test_set(jsonl, limit):
    if jsonl:
        text = Path(jsonl).read_text(encoding="utf-8")
    else:
        with urllib.request.urlopen(GSM8K_URL, timeout=60) as response:
            text = response.read().decode("utf-8")
    samples = [json.loads(line) for line in text.splitlines() if line.strip()]
    return samples[:limit]


def extract_number(text):
    boxed = re.findall(r"\\boxed\{([^{}]+)\}", text)
    if boxed:
        text = boxed[-1]
    numbers = re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text)
    return numbers[-1].replace(",", "") if numbers else None


def query(prompt, args):
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": args.max_tokens,
    }
    request = urllib.request.Request(
        args.url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + args.api_key},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=900) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--label", default="ornith-1.5-9b-obliterated")
    parser.add_argument("--mode", default="no-think", choices=["no-think", "think"])
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--jsonl", default=None)
    parser.add_argument("--outdir", default="eval-results/custom")
    parser.add_argument("--machine", default="oc-node-02")
    args = parser.parse_args()

    samples = load_test_set(args.jsonl, args.limit)
    output_dir = Path(args.outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ("gsm8k-%s-%s-%d.jsonl" % (args.label, args.mode, args.limit))

    correct = 0
    elapsed_total = 0.0
    output_tokens = 0
    with output_path.open("w", encoding="utf-8") as output:
        for index, sample in enumerate(samples):
            result, elapsed = query(sample["question"] + PROMPT_SUFFIX, args)
            message = result["choices"][0]["message"]
            content = message.get("content") or ""
            reasoning = message.get("reasoning_content") or ""
            usage = result.get("usage", {})
            prediction = extract_number(content)
            target = sample["answer"].rsplit("####", 1)[-1].strip().replace(",", "")
            passed = prediction == target
            correct += int(passed)
            elapsed_total += elapsed
            output_tokens += usage.get("completion_tokens", 0)
            output.write(json.dumps({
                "index": index,
                "question": sample["question"],
                "target": target,
                "prediction": prediction,
                "passed": passed,
                "elapsed_seconds": round(elapsed, 3),
                "output_tokens": usage.get("completion_tokens"),
                "content": content,
                "reasoning": reasoning,
                "finish_reason": result["choices"][0].get("finish_reason"),
            }, ensure_ascii=False) + "\n")
            output.flush()
            print("%d/%d %s target=%s prediction=%s time=%.2fs tokens=%s" % (
                index + 1, args.limit, "PASS" if passed else "FAIL",
                target, prediction, elapsed, usage.get("completion_tokens", 0)))

    print(json.dumps({
        "machine": args.machine,
        "mode": args.mode,
        "model": args.label,
        "engine": "llama.cpp",
        "correct": correct,
        "total": args.limit,
        "accuracy": correct / args.limit,
        "average_seconds": elapsed_total / args.limit,
        "average_output_tokens": output_tokens / args.limit,
        "results": str(output_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
