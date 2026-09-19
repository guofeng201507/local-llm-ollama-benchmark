"""Score an existing IFEval responses.jsonl with Google's official evaluator.

Why this exists: eval_ifeval_ollama.py generates and scores in one pass using
Ollama's API. Responses generated elsewhere (llama.cpp / any OpenAI-compatible
server) still need Google's official scorer, and routing them back through the
Ollama runner is unsafe -- its cache path re-queries a local Ollama for records
flagged as truncated, which would silently mix engines in one result set.

Reuses score() and read_jsonl() from eval_ifeval_ollama.py, so the grading code
is identical to the Ollama rows; only the transport differs.

Run from the repo root with the eval venv:
    .venv-eval/bin/python score_ifeval_existing.py <results-dir> "<sampling note>" [model]

<results-dir> must contain input_data.jsonl and responses.jsonl, with record
fields key / prompt / response / elapsed_seconds / output_tokens / done_reason.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
import eval_ifeval_ollama as base  # noqa: E402

outdir = Path(sys.argv[1])
sampling = sys.argv[2] if len(sys.argv) > 2 else "n/a"
model = sys.argv[3] if len(sys.argv) > 3 else "unknown"

records = base.read_jsonl(outdir / "responses.jsonl")
count = len(records)
summary = {
    "model": model,
    "engine": "llama.cpp",
    "dataset": "IFEval fixed leading subset",
    "samples": count,
    "sampling": sampling,
    "average_seconds": sum(r["elapsed_seconds"] for r in records) / count,
    "average_output_tokens": sum(r["output_tokens"] for r in records) / count,
    "truncated": sum(r["done_reason"] == "length" for r in records),
    "scores": base.score(outdir / "input_data.jsonl", outdir / "responses.jsonl", outdir),
}
(outdir / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
