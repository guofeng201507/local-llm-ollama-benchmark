# IFEval 严格指令遵循测试

测试日期：2026-07-27  
设备：Apple M3，24 GB 统一内存  
推理框架：Ollama  
数据与评分器：Google Research `instruction_following_eval`

## 结论

这轮已经测试 IFEval，但不是完整 541 题榜单，而是官方数据文件固定前
10 条的快速可用性测试，共包含 18 条可机器验证的指令。

| 模型 | Strict 题级 | Strict 指令级 | Loose 题级 | Loose 指令级 | 平均耗时 | 平均输出 | 截断 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5 9B | 10/10 | 18/18 | 10/10 | 18/18 | 64.5 秒 | 271 tokens | 0 |
| Qwen3 8B | 8/10 | 16/18 | 8/10 | 16/18 | 54.3 秒 | 310 tokens | 0 |
| Nanbeige4.2 3B Q6 | 8/10 | 15/18 | 8/10 | 16/18 | 78.7 秒 | 434 tokens | 0 |
| Qwen3.5 4B | 7/10 | 15/18 | 7/10 | 15/18 | 50.6 秒 | 422 tokens | 1 |
| Gemma 4 E4B | 6/10 | 13/18 | 6/10 | 13/18 | 46.3 秒 | 363 tokens | 0 |

本轮最强的是 Qwen3.5 9B，18 条指令全部通过，但也是标准 Ollama
模型中最慢的。Qwen3 8B 得分略低，速度与质量更均衡。Gemma E4B 最快，
但严格遵循率最低。

Nanbeige Q6 的指令遵循能力并不差：Strict 题级与 Qwen3 8B 同为 8/10，
Loose 指令级也同为 16/18。不过它平均 78.7 秒/题，是五个模型中最慢，
平均输出也最长。结合此前 GSM8K 与 BFCL 结果，它仍不适合作为日常默认
模型；更合理的定位是架构研究和兼容性实验。

Qwen3.5 4B 在最后一题即使把上限从 1024 提高到 2048 tokens，仍然触发
长度截断。分数在重跑前后均为 7/10、15/18，但这次失控长输出应被视为
实际可用性缺陷。

## 测试口径

- 固定样本：官方 `input_data.jsonl` 前 10 条，不随机抽样。
- 推理：`temperature=0`、`think=false`、`num_ctx=4096`。
- 输出上限：Qwen3.5 4B/9B 和 Nanbeige Q6 为 2048 tokens；Qwen3 8B
  与 Gemma E4B 实际使用 1024 tokens，且均未截断。
- Nanbeige 使用专用 Ollama 分支服务端口 `11435`；其他模型使用标准
  Ollama 服务端口 `11434`。
- Strict 是原始响应的精确约束检查；Loose 会尝试移除 Markdown 围栏、
  前后说明等轻微包装后再检查。
- 题级只有在一题内全部指令通过时才算正确；指令级按每个单独约束计分。
- 平均耗时包含本机请求到完整响应返回的墙钟时间，不是跨设备性能指标。

## 失败类型观察

这个固定子集主要覆盖大小写、分段、项目符号、关键词、字数、标点和
首尾格式等要求。失败集中在：

- 英文全大写或大写词频要求；
- 指定章节数、项目符号列表数；
- 必须包含关键词或禁止逗号；
- 回复必须由引号包围。

Nanbeige 在 Strict 与 Loose 指令级之间相差一条，说明它有一次更像是
答案外围格式造成的失败。其余四个模型的 Strict 与 Loose 完全一致，
失败更多来自真正遗漏约束，而非 Markdown 包装。

## 复现

官方源码与数据不提交到仓库，可用 sparse checkout 准备：

```bash
git clone --depth 1 --filter=blob:none --sparse \
  https://github.com/google-research/google-research.git \
  eval-data/google-research
git -C eval-data/google-research sparse-checkout set \
  instruction_following_eval
```

安装依赖后，还需把 NLTK `punkt_tab` 数据放到
`eval-data/nltk_data/tokenizers/punkt_tab`，或者安装到 NLTK 的标准数据
目录。运行示例：

```bash
.venv-eval/bin/python eval_ifeval_ollama.py \
  --model qwen3:8b \
  --label qwen3-8b \
  --limit 10 \
  --max-tokens 2048
```

Nanbeige 示例：

```bash
.venv-eval/bin/python eval_ifeval_ollama.py \
  --model nanbeige4.2:3b-q6 \
  --label nanbeige4.2-3b-q6 \
  --url http://127.0.0.1:11435/api/chat \
  --limit 10 \
  --max-tokens 2048
```

运行器会保存输入、原始响应、Strict/Loose 逐题结果和汇总 JSON；已有完整
响应会直接复用。若提高 `--max-tokens`，之前因长度上限截断的条目会单独
重跑。

## 局限

10 题结果只能用于发现明显问题，不能替代完整 541 题 IFEval。尤其
Qwen3.5 9B 的 100% 不应直接理解为完整榜单也会满分。模型之间还使用了
不同输出上限，不过除 Qwen3.5 4B 外没有任何截断，因此没有观察到上限
直接影响其他模型得分。

下一步若要形成可发布的模型排名，应至少扩大到固定 50–100 题，最好跑完
全部 541 题，并固定 Ollama 版本、模型摘要、量化、输出上限和设备状态。
