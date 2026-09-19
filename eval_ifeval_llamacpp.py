#!/usr/bin/env python3
"""Generate IFEval responses from llama.cpp in the layout eval_ifeval_ollama.py scores.

Scoring is deliberately NOT done here.  It needs Google's official evaluator
plus immutabledict / langdetect / nltk, and the Ollama runner already reports
those numbers from a responses.jsonl.  So: generate on the machine that serves
the model, then score wherever that environment already exists.

Records are written with the same field names the Ollama runner uses
(key, prompt, response, elapsed_seconds, output_tokens, done_reason) so the two
engines stay interchangeable.

Sampling note: only `temperature` is sent per request.  The other sampling
parameters (top_k / top_p / min_p / presence_penalty / repeat_penalty) are set as
llama-server defaults on the command line, so the exact settings are visible in
the launch command and cannot be silently ignored by the request parser.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def query(url: str, api_key: str, prompt: str, max_tokens: int,
          temperature: float) -> tuple[dict[str, Any], float]:
    payload = {"messages": [{"role": "user", "content": prompt}],
               "temperature": temperature, "max_tokens": max_tokens}
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + api_key},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=1800) as response:
        result = json.load(response)
    return result, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8090")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--label", default="ornith-1.5-9b-obliterated")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--input-data", type=Path, required=True)
    parser.add_argument("--outdir-base", type=Path, default=Path("eval-results/ifeval"))
    parser.add_argument("--engine", default="llama.cpp")
    parser.add_argument("--sampling-note", default="server defaults")
    args = parser.parse_args()

    selected = read_jsonl(args.input_data)[: args.limit]
    output_dir = args.outdir_base / f"{args.label}-{args.limit}"
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs_path = output_dir / "input_data.jsonl"
    responses_path = output_dir / "responses.jsonl"

    with inputs_path.open("w", encoding="utf-8") as output:
        for item in selected:
            output.write(json.dumps(item, ensure_ascii=False) + "\n")

    records = read_jsonl(responses_path) if responses_path.exists() else []
    complete_cache = len(records) == len(selected) and all(
        record.get("key") == item["key"] and record.get("prompt") == item["prompt"]
        for record, item in zip(records, selected)
    )
    if complete_cache:
        print(f"Reusing {len(records)} cached responses from {responses_path}")
    else:
        records = []
        with responses_path.open("w", encoding="utf-8") as output:
            for index, item in enumerate(selected, 1):
                result, elapsed = query(args.url, args.api_key, item["prompt"],
                                        args.max_tokens, args.temperature)
                choice = result["choices"][0]
                message = choice.get("message", {})
                record = {
                    "key": item["key"],
                    "prompt": item["prompt"],
                    "response": message.get("content") or "",
                    "reasoning_chars": len(message.get("reasoning_content") or ""),
                    "elapsed_seconds": round(elapsed, 3),
                    "output_tokens": result.get("usage", {}).get("completion_tokens", 0),
                    "done_reason": choice.get("finish_reason"),
                }
                records.append(record)
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
                output.flush()
                print(f"{index}/{args.limit} key={item['key']} time={elapsed:.2f}s "
                      f"tokens={record['output_tokens']} done={record['done_reason']} "
                      f"reasoning_chars={record['reasoning_chars']}", flush=True)

    elapsed_total = sum(item["elapsed_seconds"] for item in records)
    output_tokens = sum(item["output_tokens"] for item in records)
    print(json.dumps({
        "model": args.label, "engine": args.engine,
        "dataset": "IFEval fixed leading subset",
        "samples": len(selected), "temperature": args.temperature,
        "sampling": args.sampling_note, "max_tokens": args.max_tokens,
        "average_seconds": elapsed_total / len(selected),
        "average_output_tokens": output_tokens / len(selected),
        "truncated": sum(item["done_reason"] == "length" for item in records),
        "mean_reasoning_chars": sum(item.get("reasoning_chars", 0) for item in records) / len(records),
        "responses": str(responses_path),
        "note": "generation only; score with eval_ifeval_ollama.py via Google's evaluator",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
