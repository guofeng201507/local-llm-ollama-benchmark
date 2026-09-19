# Qwen3.5-9B-abliterated 在 AMD 迷你主机上的测试（三方对比与选型结论）

测试日期：2026-09-19  
设备：AMD Ryzen 5 7640HS 迷你主机（`oc-node-02`），Radeon 760M 核显  
运行时：llama.cpp 自编译 Vulkan 后端（不是 Ollama）  
模型：`lukey03/Qwen3.5-9B-abliterated`，量化 `Q4_K_M`，5.24 GiB  
基座：`Qwen/Qwen3.5-9B`（官方权重，非 Ornith 等第三方权重）

本文把本机三个 abliterated 候选放在一起选型。三者都是同机、同 llama.cpp、同一套
runner、同一批题，并**各自按自己卡片（或基座卡片）的推荐采样**运行。

## 选型结论

**本地端点建议使用 Qwen3.5-9B-abliterated（lukey03 版）。**

决定性的依据是拒答指标，因为本端点的用途就是 uncensored 内容生成；这一项样本量
最大（520 条），也是三者差异唯一超出噪声的部分：

- **首句硬拒绝 0 次**（与 Qwen3-8B 消融版并列，Ornith 为 12 次）；
- **zou 口径拒绝率 2.31%**，三者最低；
- 它命中的标记**只有 `illegal` 这一个词**（12 次），没有任何 `Sorry` / `I cannot`
  之类的道歉或拒绝短语；另两个模型分别还有 `unethical`、`I cannot`、`Sorry` 等命中；
- **81.5% 的回答以肯定语开头**（Ornith 51.9%、Qwen3-8B 消融版 26.2%）。

能力项上它与 Qwen3-8B 消融版互有胜负，且差距落在噪声带内（见下）；而它在
**IFEval 上最快、最简洁、零截断**（17.9 秒 / 220 tokens，对比 29.0/365 与 70.9/803）。
也就是说它在关键指标更好的同时，单位时间产出更高、占用上下文更少。

额外一点：它达到这个结果是**在 Q4_K_M 上**，比另两个低一个量化档。

## 为什么选 lukey03 这个版本

Qwen3.5-9B 的 abliterated 版本不少，按「最可信」筛出两个候选：

| 候选 | 卡片证据 | 判断 |
|---|---|---|
| `huihui-ai/Huihui-Qwen3.5-9B-abliterated`（GGUF 由 mradermacher 量化，5.6 万下载） | 卡片自称 *"a crude, proof-of-concept implementation"*，**没有任何评测** | 最权威、下载最多，但自述粗糙 |
| **`lukey03/Qwen3.5-9B-abliterated`** | 完整公布两阶段方法：3 轮正交投影消融（32 层、每轮 64 个权重矩阵、同时针对 DeltaNet 的 `linear_attn.out_proj` 与 `self_attn.o_proj`）+ **QLoRA 阶段清除 5 类残留拒绝**；给出 0/18 → 7 → 9 → 13 → **18/18** 的阶段结果、与 Dolphin-Mistral 7B 的对照、8 类能力抽查，并说明**第 4 轮会把模型彻底毁掉** | 证据最完整，故选它 |

一个补充事实：`prithivMLmods/Qwen3.5-9B-abliterated-v2-MAX` 明确写着
"No changes to weights or core architecture"，它只是把 huihui-ai 版本重新分片打包，
不是另一个权重，因此不构成第三个候选。

代价：lukey03 只提供 F16 / Q4_K_M，**没有 Q5_K_M**，所以这一行比另两行低一个量化档。

## 采样设置（先查卡片，再开测）

`Qwen/Qwen3.5-9B` 官方卡片给出的推荐：

| 模式 | 推荐参数 |
|---|---|
| **Instruct / 非思考，通用任务** | `temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0` |
| 思考，通用任务 | `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0` |

两个要点：

1. **Qwen3.5 默认开启思考**，关闭需要硬开关
   `chat_template_kwargs: {"enable_thinking": false}`。
2. **Qwen3.5 不支持 Qwen3 的软开关** `/think` 和 `/nothink`，卡片原文：
   「Qwen3.5 does not officially support the soft switch of Qwen3」。
   所以 lukey03 卡片里"在提示词末尾加 `/no_think`"的建议**在 Qwen3.5 上无效**，
   那是 Qwen3 时代的写法。

顺带一个旁证：Ornith 卡片推荐的 `temp=1.0, top_p=0.95, top_k=20, min_p=0.0,
presence_penalty=1.5, repetition_penalty=1.0` 与 Qwen3.5 的"思考/通用"预设**完全一致**，
与它是 Qwen3.5 架构相符。

## 三方对比

| 指标 | Ornith-1.5-9B-OBLITERATED<br>Q5_K_M 6.19 GiB | mlabonne Qwen3-8B-abliterated<br>Q5_K_M 5.45 GiB | **lukey03 Qwen3.5-9B-abliterated<br>Q4_K_M 5.24 GiB** |
|---|---:|---:|---:|
| **AdvBench 520 首句硬拒绝** | 12（2.31%） | **0（0.0%）** | **0（0.0%）** |
| **AdvBench zou 拒绝率** | 5.38% | 3.65% | **2.31%** |
| 命中的拒绝标记 | `illegal` 27、`unethical` 2、`I cannot` 1 | `illegal` 17、`Sorry` 1、`I'm sorry` 1、`I'm just` 1 | **仅 `illegal` 12** |
| 以肯定语开头 | 51.9% | 26.2% | **81.5%** |
| 规避套话率 | 0（50 条长回答） | 0.19%（1/520） | 0.19%（1/520） |
| 输出词数中位数 | 46 | 48 | 41 |
| GSM8K 普通，前 10 题 | **7/10** | 6/10 | **7/10** |
| GSM8K 思考，前 3 题 | **3/3**（※） | 2/3 | **3/3** |
| BFCL simple_python，前 20 题 | 15/20 | **17/20** | 15/20 |
| IFEval Strict，前 10 题 | 4/10，11/18 | **5/10，12/18** | **5/10，12/18** |
| IFEval 平均耗时 / 输出 | 70.9 秒 / 803 tokens | 29.0 秒 / 365 tokens | **17.9 秒 / 220 tokens** |
| IFEval 截断数 | 2 | 1 | **0** |
| BFCL 平均耗时 / 输出 | 9.9 秒 / 77.0 tokens | **3.7 秒 / 30.9 tokens** | 6.4 秒 / 50.5 tokens |

※ Ornith 的思考格是在 `temp=0` 下测的（当时尚未读卡片），不是严格同口径，仅供参考。

### 怎么看这张表

- **可以当结论的**：拒答三项（n=520）。三个模型里只有它们拉开到噪声之外，
  且 Qwen3.5-9B 消融版是唯一一个**只命中假阳性词 `illegal`、零道歉短语**的模型。
- **不能当结论的**：GSM8K 7 vs 6、思考 3/3 vs 2/3、IFEval 5/10 vs 5/10。
  本机已实测同一配置重复运行会漂移 ±1 题（Ornith 两次同一配置得到 4/10 与 5/10），
  所以这类一题之差不足以判定优劣。
- **真实且差距较大的**：IFEval 的速度与输出长度（17.9 秒/220 tokens 对 70.9 秒/803 tokens）。
  这不是噪声，是模型风格差异——Ornith 更啰嗦。

## 拒答与规避（决定性指标）

同一套 `abliterated_eval.py`、同一 `max_tokens=64`、同一 `temperature=0`、同一 4 并发，
三个模型完全同口径。

| | Ornith | Qwen3-8B-abl | Qwen3.5-9B-abl |
|---|---:|---:|---:|
| 首句硬拒绝（强短语） | 12（2.31%） | **0** | **0** |
| zou 子串口径 | 28（5.38%） | 19（3.65%） | **12（2.31%）** |
| 未截断比例 | ≈0.2% | 18.3% | **0.0%** |
| 以肯定语开头 | 51.9% | 26.2% | **81.5%** |

注意最后一行：Qwen3.5-9B 消融版的 520 条回答**全部**触到 64-token 上限，
未截断比例为 0——它是三个里最"不停手、一直写"的，这与 `starts_affirmative` 高达
81.5% 一致，即在 64 token 的窗口内几乎都在正面作答。

同时提醒：lukey03 卡片建议配一条"uncensored 系统提示词"以加强不拒绝行为。
本次为与另两个模型保持同口径，**没有加系统提示词**（三者都只发一条 user 消息），
所以这里的数字是"裸提示"下的结果，实际使用加系统提示词可能更宽松。

## 局限

- GSM8K 10 题、思考 3 题、BFCL 20 题、IFEval 10 题都是小样本；已实测同配置重复
  运行会漂移 ±1 题，因此这些项只能看趋势，不能定胜负。
- 本行是 Q4_K_M，另两行是 Q5_K_M，量化档不同；量化会影响拒答与能力，故严格来说
  这三行不是完全同量化对比（这一点对 Qwen3.5-9B 消融版是不利条件，它仍然赢下拒答）。
- 拒答臂用 `temperature=0`，与三个卡片各自推荐的采样都不同；但三者同设置，
  所以横向对比成立，绝对值不代表各自最优采样下的拒答率。
- Ornith 的思考格为 `temp=0`，非严格同口径。
- 未评估内容质量（连贯性、事实性），只测拒答与基准正确率。
- 未测试 lukey03 卡片建议的系统提示词变体。

## 相关数据

- `eval-results/custom/gsm8k-lukey03-qwen3.5-9b-abliterated-{no-think-10,think-3}.jsonl`
- `eval-results/tool-calling/bfcl-v4-simple-python-lukey03-qwen3.5-9b-abliterated-n20-o0.jsonl`
- `eval-results/ifeval/lukey03-qwen3.5-9b-abliterated-10/`
- `eval-results/safety/advbench-*.json`（只有汇总指标，不含任何模型生成文本）
