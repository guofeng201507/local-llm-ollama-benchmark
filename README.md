# Local LLM Ollama Benchmark

这是一次在 Apple M3、24 GB 统一内存设备上进行的本地小模型可用性测试。
项目记录了 Nanbeige、Gemma 和 Qwen 系列在 Ollama 中运行 GSM8K
小样本时的正确率、延迟、输出长度和思考模式停止行为。

## 核心结果

| 模型 | 普通模式 | 思考模式 | 建议 |
|---|---:|---:|---|
| Qwen3 8B | 10/10 | 1/3 | 日常使用关闭思考 |
| Gemma 4 E4B | 6/10 | 3/3 | 显式思考最稳定 |
| Qwen3.5 4B | 4/10 | 1/3 | 快速轻量任务 |
| Qwen3.5 9B | 2/10 | 1/3 | 当前 Ollama 模板下不推荐 |
| Nanbeige4.2 Q6 | 2/10 | 2/3 | 仅建议研究和实验 |

普通模式使用固定 GSM8K 前 10 题，思考模式使用相同的前 3 题。这是一轮
用于发现明显可用性问题的小样本测试，并非完整模型排行榜。

作为非本地参考，指定 `gpt-5.6-sol` 的 Codex 独立代理在相同 10 题上得到
10/10，并严格遵守只输出答案的格式。由于无法取得与 Ollama 同口径的延迟、
吞吐、内存和 Token 数据，它不参与本地性能排名。

完整测试过程、参数、结果解释和局限见：

- [2026-07-26 本地小模型测试总结](2026-07-26-local-model-test-summary.md)
- [Nanbeige 本地运行笔记](NANBEIGE42-NOTES.md)

总结文档的“后续测试集与评测路线图”记录了 IFEval、EvalPlus、C-Eval、
CMMLU、BFCL、LongBench、EvalScope 和 lm-evaluation-harness，供后续扩展
指令遵循、代码、中文知识、工具调用与长上下文测试。

## 运行评测

准备 Python 环境：

```bash
python3 -m venv .venv-eval
.venv-eval/bin/pip install -r requirements.txt
```

普通模式示例：

```bash
.venv-eval/bin/python eval_gsm8k_ollama.py \
  --model qwen3:8b \
  --url http://127.0.0.1:11434/api/chat \
  --label qwen3-8b \
  --limit 10 \
  --max-tokens 512
```

思考模式示例：

```bash
.venv-eval/bin/python eval_gsm8k_ollama.py \
  --model qwen3:8b \
  --url http://127.0.0.1:11434/api/chat \
  --label qwen3-8b \
  --limit 3 \
  --think \
  --max-tokens 1024
```

脚本默认从 `eval-data/datasets/` 读取已由 EvalScope 下载的 GSM8K 测试集。

## 目录

```text
.
├── 2026-07-26-local-model-test-summary.md
├── NANBEIGE42-NOTES.md
├── eval_gsm8k_ollama.py
├── eval_nanbeige_smoke.py
├── eval-results/
├── requirements.txt
└── run-nanbeige-ollama.sh
```

模型权重、虚拟环境、第三方源码和数据集缓存不会提交到仓库。
