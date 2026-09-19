# Local LLM Ollama Benchmark

这是一组本地小模型的可用性测试，目前覆盖两台机器：

- **Apple M3，24 GB 统一内存**，用 Ollama 跑：Nanbeige、Gemma、Qwen 系列的
  GSM8K 正确率、延迟、输出长度和思考模式停止行为；
- **AMD Ryzen 5 7640HS 迷你主机，约 18.8 GiB 可用内存**，用 llama.cpp + Vulkan 跑：
  与上面同口径的 GSM8K 横向对比，外加 AdvBench / HarmBench 拒答率与规避行为测量。

## 核心结果

### Apple M3（Ollama）

| 模型 | 普通模式 | 思考模式 | 建议 |
|---|---:|---:|---|
| Qwen3 8B | 10/10 | 1/3 | 日常使用关闭思考 |
| Gemma 4 E4B | 6/10 | 3/3 | 显式思考最稳定 |
| Qwen3.5 4B | 4/10 | 1/3 | 快速轻量任务 |
| Qwen3.5 9B | 2/10 | 1/3 | 当前 Ollama 模板下不推荐 |
| Nanbeige4.2 Q6 | 2/10 | 2/3 | 仅建议研究和实验 |

### AMD Ryzen 5 7640HS（llama.cpp + Vulkan）

| 模型 | GSM8K普通10 | GSM8K思考3 | BFCL20 | IFEval Strict题级 | IFEval Strict指令级 |
|---|---:|---:|---:|---:|---:|
| Ornith-1.5-9B-OBLITERATED Q5_K_M | 4–5/10 | 3/3 | 16/20 | 4/10 | 11/18 |

工具调用（16/20）与思考数学（3/3）都是并列第一，普通数学中游，但严格指令遵循
是全部被测模型里最差的（4/10）。GSM8K 同一配置连跑两次得到 4/10 与 5/10，
说明 ±1 题属噪声。四项测试均为单并发；IFEval 一行用的是该模型卡片推荐的采样
（`temp=1.0 top_p=0.95 top_k=20 presence_penalty=1.5`），换用推荐采样后 IFEval 从
3/10 升到 4/10，其余仍偏低。该模型的原生思考模式在本机不可用（单题推理就超过
4096 token），详见 AMD 测试文档。

同一台 AMD 机器还量化了 abliterated 是否真的生效：AdvBench 全量 520 题
首句硬拒绝 12 次（其中只有 1 次出现 `I cannot`），HarmBench `standard` 全量
200 题 1 次；50 条长回答中规避套话 0 命中；单流解码 11.6 tok/s，4 并发聚合 23.0 tok/s。

普通模式使用固定 GSM8K 前 10 题，思考模式使用相同的前 3 题。这是一轮
用于发现明显可用性问题的小样本测试，并非完整模型排行榜。两台机器的引擎
不同（Ollama / llama.cpp），正确率可比，**耗时不可直接对比**。

作为非本地参考，指定 `gpt-5.6-sol` 的 Codex 独立代理在相同 10 题上得到
10/10，并严格遵守只输出答案的格式。由于无法取得与 Ollama 同口径的延迟、
吞吐、内存和 Token 数据，它不参与本地性能排名。

完整测试过程、参数、结果解释和局限见：

- [2026-07-26 本地小模型测试总结](2026-07-26-local-model-test-summary.md)
- [2026-07-26 BFCL 工具调用测试总结](2026-07-26-bfcl-tool-calling-summary.md)
- [2026-07-27 IFEval 严格指令遵循测试](2026-07-27-ifeval-summary.md)
- [2026-08-19 Qwen3.8 27B Uncensored Q4_K_S 测试](2026-08-19-qwen3.8-27b-uncensored-q4ks.md)
- [2026-08-19 Qwen3.8 27B 官方权重与 Uncensored 对比](2026-08-19-qwen3.8-27b-official-vs-uncensored.md)
- [2026-08-19 全部本地模型综合对比](2026-08-19-all-local-models-comparison.md)
- [2026-09-19 AMD 迷你主机 Ornith-1.5-9B-OBLITERATED 测试](2026-09-19-amd-ryzen-7640hs-ornith-1.5-9b-abliterated.md)
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
IFEval 运行器使用 Google Research 官方数据和评分代码；具体准备方法与命令
见 IFEval 总结文档。

llama.cpp 的对应运行器 `eval_gsm8k_llamacpp.py` 复用同一套提示词与答案提取
逻辑，直接调用 OpenAI 兼容接口，并且默认从官方 URL 取数据集，不需要 HF 缓存：

```bash
python3 eval_gsm8k_llamacpp.py \
  --limit 10 \
  --url http://127.0.0.1:8090 \
  --api-key "$LLAMA_API_KEY" \
  --mode no-think \
  --max-tokens 512
```

注意 llama.cpp 没有按请求切换思考的开关：思考由服务端 `--reasoning on|off`
决定，思路文本回到 `message.reasoning_content`（Ollama 是 `message.thinking`），
所以思考模式要另跑一次服务端配置。

## 目录

```text
.
├── 2026-07-26-local-model-test-summary.md
├── 2026-07-26-bfcl-tool-calling-summary.md
├── 2026-07-27-ifeval-summary.md
├── 2026-08-19-qwen3.8-27b-uncensored-q4ks.md
├── 2026-08-19-qwen3.8-27b-official-vs-uncensored.md
├── 2026-08-19-all-local-models-comparison.md
├── 2026-09-19-amd-ryzen-7640hs-ornith-1.5-9b-abliterated.md
├── NANBEIGE42-NOTES.md
├── eval_bfcl_ollama.py
├── eval_gsm8k_llamacpp.py
├── eval_gsm8k_ollama.py
├── eval_ifeval_ollama.py
├── eval_nanbeige_smoke.py
├── eval-results/
├── requirements.txt
└── run-nanbeige-ollama.sh
```

模型权重、虚拟环境、第三方源码和数据集缓存不会提交到仓库。
