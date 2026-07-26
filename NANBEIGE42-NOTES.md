# Nanbeige4.2-3B local run

The stock Ollama 0.32.1 installed on this Mac cannot load this model:

```text
unknown model architecture: 'nanbeige'
```

The compatible Nanbeige forks were built in:

- `vendor/nanbeige-llama.cpp`
- `vendor/nanbeige-ollama`

The retained Q6_K model has the short local name:

```text
nanbeige4.2:3b-q6
```

Start the compatible server (it uses port 11435 to avoid the stock Ollama
service on port 11434):

```bash
./run-nanbeige-ollama.sh
```

In another terminal:

```bash
OLLAMA_HOST=127.0.0.1:11435 \
  ./vendor/nanbeige-ollama/ollama run nanbeige4.2:3b-q6
```

Enable thinking for reasoning tasks:

```bash
OLLAMA_HOST=127.0.0.1:11435 \
  ./vendor/nanbeige-ollama/ollama run nanbeige4.2:3b-q6 --think=true --hidethinking
```

Observed on Apple M3 (10-core GPU), Q6_K:

- Model file: 3.4 GB
- Loaded size reported by Ollama: 4.2 GB
- Processor: 100% GPU
- Generation: approximately 9-15 tokens/s in the tested runs

The model is capable for its size, but it is verbose in thinking mode and
made a basic decimal-comparison error with thinking disabled. Enable thinking
for reasoning tasks and validate important outputs.

## Evaluation baseline

EvalScope 1.9.1 is installed in `.venv-eval`. The initial GSM8K smoke test
produced:

- Ollama native API, thinking disabled, zero-shot: 2/10 correct
- Ollama native API, thinking enabled, zero-shot: 2/3 correct
- Thinking disabled: 2.87 seconds and 32 output tokens per question on average
- Thinking enabled: 170.33 seconds and 585 output tokens per question on average

The third thinking-mode question reached the 1024-token output limit before
emitting its final answer. The reasoning contained the correct calculation,
but the strict benchmark correctly scored the empty final answer as wrong.

Run the practical native-Ollama test with:

```bash
.venv-eval/bin/python eval_gsm8k_ollama.py --limit 10 --max-tokens 128
.venv-eval/bin/python eval_gsm8k_ollama.py --limit 3 --think --max-tokens 1024
```

The EvalScope smoke test, result files, and HTML report are under
`eval-results/`.

## Gemma 4 E4B comparison

Google Gemma 4 E4B was tested on the identical leading GSM8K samples with the
same prompt, temperature 0, and 4096-token runtime context:

- Local Ollama tag: `gemma4:e4b`
- Ollama metadata: 8.0B total parameters, Q4_K_M
- Loaded size: 3.3 GB, 100% GPU
- Thinking disabled, 512-token limit: 6/10 correct
- Thinking enabled, 1024-token limit: 3/3 correct
- Thinking disabled: 22.62 seconds and 353 output tokens per question
- Thinking enabled: 59.00 seconds and 515 output tokens per question

At the original 128-token limit Gemma scored 0/10 because all ten responses
were truncated before the final answer. That run demonstrates poor compliance
with the request to output only the answer, but it is not a fair measure of
math accuracy. The 512-token run is used for the accuracy comparison.

On the paired three thinking-mode questions, Nanbeige scored 2/3 at 170.33
seconds per question, while Gemma scored 3/3 at 59.00 seconds per question.

## Qwen3.5 4B comparison

Official Ollama `qwen3.5:4b` was tested with the same samples and settings:

- Ollama metadata: 4.7B parameters, Q4_K_M
- Loaded size: 3.2 GB, 100% GPU
- Thinking disabled, 512-token limit: 4/10 correct
- Thinking enabled, 1024-token limit: 1/3 correct
- Thinking disabled: 4.25 seconds and 44 output tokens per question
- Thinking enabled: 79.46 seconds and 807 output tokens per question

In thinking mode, two questions exhausted all 1024 tokens before emitting a
final answer. On this small sample Qwen was faster and more concise than Gemma
without thinking, but less accurate. Its thinking mode was counterproductive
with the default Ollama template and parameters.

## Qwen3.5 9B comparison

The official `qwen3.5:9b` model, rather than the locally present abliterated
community variant, was tested with the same samples:

- Ollama metadata: 9.7B parameters, Q4_K_M
- Loaded size: 5.6 GB, 100% GPU
- Thinking disabled, 512-token limit: 2/10 correct
- Thinking enabled, 1024-token limit: 1/3 correct
- Thinking disabled: 2.03 seconds and 4.7 output tokens per question
- Thinking enabled: 70.23 seconds and 806 output tokens per question

The two failed thinking-mode questions contained the correct calculation in
the hidden reasoning but never emitted a final response. A separate 2048-token
diagnostic did not fix this: it still scored 1/3, averaged 203.48 seconds and
1488 output tokens, and both failed questions exhausted 2048 tokens.

Under the same 1024-token thinking budget, Gemma 4 E4B scored 3/3 at 59.00
seconds per question, while official Qwen3.5 9B scored 1/3 at 70.23 seconds.
This indicates a stopping/template failure in Qwen3.5 9B's thinking mode under
Ollama 0.32.1, not simply insufficient mathematical knowledge.

## Qwen3 8B comparison

Official `qwen3:8b` was tested with the same samples and settings:

- Ollama metadata: 8.2B parameters, Q4_K_M
- Loaded size: 5.9 GB, 100% GPU
- Thinking disabled, 512-token limit: 10/10 correct
- Thinking enabled, 1024-token limit: 1/3 correct
- Thinking disabled: 16.43 seconds and 188 output tokens per question
- Thinking enabled: 64.08 seconds and 803 output tokens per question

Qwen3 8B was the first tested model to answer all ten no-thinking questions
correctly. Explicit thinking was counterproductive: two responses repeatedly
rechecked already-correct calculations until the 1024-token limit. Under this
Ollama setup, Qwen3 8B should be used with thinking disabled for routine math.

Compared with Gemma 4 E4B, Qwen3 8B won the practical no-thinking test
(10/10 versus 6/10) and was faster (16.43 versus 22.62 seconds per question).
Gemma won the explicit-thinking test (3/3 versus 1/3) and stopped reliably.
