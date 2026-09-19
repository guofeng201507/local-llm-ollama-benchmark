# Abliterated Qwen3-8B 在 AMD 迷你主机上的测试（与 Ornith-1.5-9B-OBLITERATED 对比）

测试日期：2026-09-19  
设备：AMD Ryzen 5 7640HS 迷你主机（`oc-node-02`），Radeon 760M 核显  
系统：Ubuntu 26.04.1 LTS Desktop  
运行时：llama.cpp 自编译 Vulkan 后端（不是 Ollama）  
模型：`mlabonne/Qwen3-8B-abliterated`，量化 `Q5_K_M`，5.45 GiB（GGUF 由 bartowski 提供）

本次是为回答「本地这个端点该用哪个模型」而做的同机同引擎对比。两个模型都在本机、
同一个 llama.cpp、同一套 runner、同一批题、**各自按自己卡片的推荐采样**运行。

## 结论

**建议改用 abliterated Qwen3-8B。** 它在最关键的一项上明显更好，其余项目互有胜负：

| | Ornith-1.5-9B-OBLITERATED | **abliterated Qwen3-8B** |
|---|---:|---:|
| AdvBench 520 首句硬拒绝 | 12（2.31%） | **0（0.0%）** |
| AdvBench zou 口径拒绝率 | 5.38% | **3.65%** |
| GSM8K 普通 10 题 | **7/10** | 6/10 |
| GSM8K 思考 3 题 | **3/3**（注：该格在 `temp=0` 下测的，非严格匹配） | 2/3 |
| BFCL simple_python 20 题 | 15/20 | **17/20** |
| IFEval Strict 前 10 题 | 4/10，11/18 | **5/10，12/18** |
| BFCL 平均耗时 / 输出 | 9.9 秒 / 77.0 tokens | **3.7 秒 / 30.9 tokens** |
| IFEval 平均耗时 / 输出 | 70.9 秒 / 802.6 tokens | **29.0 秒 / 365.0 tokens** |
| 文件大小 | 6.19 GiB | **5.45 GiB** |

判断依据：本端点的用途是 uncensored 内容生成，因此**拒答率是第一指标**。Qwen3-8B
消融版在 520 条标准有害指令上**没有一次首句硬拒绝**（Ornith 12 次）。同时它工具调用
更准（17/20）、严格指令遵循略好（5/10）、**每条请求快一倍以上、输出短一半**
（IFEval 365 vs 803 tokens），文件还小 0.74 GiB。代价是普通数学低一题（6 vs 7）。

## 采样设置（先查卡片，再开测）

| | 卡片推荐 |
|---|---|
| `Qwen/Qwen3-8B` 非思考模式 | `temperature=0.7, top_p=0.8, top_k=20, min_p=0` |
| `Qwen/Qwen3-8B` 思考模式 | `temperature=0.6, top_p=0.95, top_k=20, min_p=0` |
| `mlabonne/Qwen3-8B-abliterated` | `temperature=0.6, top_k=20, top_p=0.95, min_p=0` |
| `OBLITERATUS/Ornith-1.5-9B-OBLITERATED` | `temperature=1.0, top_p=0.95, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0` |

Qwen3 卡片有一句必须引用的话：

> **DO NOT use greedy decoding**, as it can lead to performance degradation and
> endless repetitions.

这在本次得到了印证。Ornith 早先按仓库惯例用 `temperature=0` 测 GSM8K 只得到
4–5/10，并出现退化重复（见 Ornith 文档）；换用卡片采样后升到 **7/10**。
`temperature=0` 对这两个模型都是错误设置，仓库里其他 `temp=0` 的历史行也应
按此保留意见。

非思考模式用 Qwen3 模板参数 `enable_thinking=false` 强制关闭——这是 Qwen3 系列的
正确机制（卡片写明默认 `enable_thinking=True`）。

## 部署结果

| 项 | 值 |
|---|---|
| 模型文件 | 5.45 GiB（5,851,113,056 bytes，已校验） |
| 架构 | Qwen3 密集模型，36 层，8.2B 参数 |
| 上下文 | 8192，KV cache `q8_0` |
| 处理器分配 | 100% GPU（Vulkan），无 CPU 卸载 |
| 模型加载 | 约 2 秒 |
| 思考模式 | 默认开启，用 `enable_thinking=false` 关闭 |

## 测试汇总

全部为单并发。非思考模式用卡片推荐采样；思考模式用思考档采样。

| 测试 | 结果 | 平均耗时 | 平均输出 |
|---|---:|---:|---:|
| GSM8K 普通模式，前 10 题 | 6/10 | 10.5 秒 | 127.1 tokens |
| GSM8K 思考模式，前 3 题 | 2/3 | 103.2 秒 | 1295.3 tokens |
| BFCL v4 simple_python，前 20 题 | 17/20 | 3.7 秒 | 30.9 tokens |
| IFEval 前 10 题 Strict | 5/10，12/18 | 29.0 秒 | 365.0 tokens |
| IFEval 前 10 题 Loose | 5/10，12/18 | 同上 | 同上 |

思考模式第 1 题用满 2048 token 仍未给出答案（截断），第 3 题耗时 130 秒。
思考模式在这台机器上依然不便宜，但没有 Ornith 那么极端（Ornith 是 4096 token
全用在推理上、`content` 为空）。

### abliteration 的代价

Mac 表里官方 Qwen3 8B（Ollama，`temp=0`）的 IFEval 是 8/10、16/18；本次消融版在
本机是 5/10、12/18。**消融让严格指令遵循大约掉了 3 题 / 4 条指令**，这与 Ornith
消融版公布的 MMLU −4pp 方向一致，说明 abliteration 并非没有代价。

（注意两者引擎与采样不同：Mac 行是 Ollama + `temp=0`，本次是 llama.cpp + 卡片采样，
所以这是趋势对比而非严格同口径。）

## 拒答与规避：AdvBench 520

同一套 `abliterated_eval.py`、同一 `max_tokens=64`、同一 `temperature=0`，
与 Ornith 那次完全同口径，因此可以直接比。

| 指标 | Ornith-1.5-9B-OBL | **Qwen3-8B-abliterated** |
|---|---:|---:|
| 首句硬拒绝（强短语） | 12（2.31%） | **0（0.0%）** |
| zou 子串口径拒绝 | 28（5.38%） | 19（3.65%） |
| 命中标记明细 | `illegal` 27、`unethical` 2、`I cannot` 1 | `illegal` 17、`Sorry` 1、`I'm sorry` 1、`I'm just` 1 |
| 规避套话率 | 0/50 长回答 | 1/520（0.19%） |
| 以肯定语开头 | 51.9% | 26.2% |
| 未截断比例 | ≈0.2% | 18.3% |
| 输出词数中位数 | 46 | 48 |

两个模型**都没有真正的硬拒绝**：Qwen3-8B 消融版的首句硬拒绝为 0，Ornith 为 12；
zou 口径两边都由 `illegal` 这个词主导（17 和 27 次），是已知的假阳性来源。
Qwen3-8B 消融版有 3 条回答带道歉语（`Sorry` / `I'm sorry` / `I'm just`），
属于「软拒绝」的候选，数量远少于 Ornith。

`starts_affirmative` 从 51.9% 降到 26.2% 不代表更差——它只是说明 Qwen3-8B 更少用
「Sure, here is…」这种套话开头，直接进入内容。

## 综合判断

> **本篇结论已被后续测试更新。** 之后又测了 `lukey03/Qwen3.5-9B-abliterated`：
> 它在拒答指标上更好（zou 口径 2.31% 对 3.65%，且只命中假阳性词 `illegal`、零道歉短语），
> 能力项与本文持平，IFEval 更快更简洁。最终选型见
> [Qwen3.5-9B-abliterated 三方对比](2026-09-19-amd-ryzen-7640hs-abliterated-qwen3.5-9b.md)。

**该端点应改用 abliterated Qwen3-8B。** 它更符合用途（零硬拒绝）、工具调用更准、
格式遵循略好、速度快一倍、输出更短更省上下文，模型文件也更小。

代价与保留：

- 普通数学低一题（6 vs 7），思考数学低一题（2/3 vs 3/3），但样本仅 10 题与 3 题；
- 它的思考模式同样偏贵（103 秒/题），不适合作为默认开启；
- 消融本身让严格指令遵循掉了约 3 题，说明它也不是「无代价的免费午餐」。

不建议把两者都常驻：18 GiB 内存装不下（6.19 + 5.45 GiB 权重已接近总量），
切换需要停服务再起，不能并行。

## 局限

- 全部是小样本：GSM8K 10 题、思考 3 题、BFCL 20 题、IFEval 10 题。n=10 时 ±1 题属噪声。
- 两个模型的 GSM8K 思考模式未在完全相同的采样下测量（Ornith 那格是 `temp=0`）。
- 只测了一个量化（Q5_K_M），只测了 BFCL `simple_python`。
- 拒答臂的 `temperature=0` 与两个卡片推荐的采样不同；但两边用的是同一设置，
  所以**两者之间的对比**仍然成立，只是绝对值不代表各自最优采样下的拒答率。
- 没有跑未消融的 Qwen3-8B 在 llama.cpp 上的同口径对照，消融代价那段是跨引擎的趋势对比。
- 未评估内容质量（连贯性、事实性），只测了拒答与基准正确率。
