# Ornith-1.5-9B-OBLITERATED Q5_K_M 在 AMD 迷你主机上的测试

测试日期：2026-09-19  
设备：AMD Ryzen 5 7640HS 迷你主机（`oc-node-02`），Radeon 760M 核显  
内存：约 18.8 GiB 可用（LPDDR5-6400，dmidecode 报 4×6 GB）  
系统：Ubuntu 26.04.1 LTS Desktop，内核 7.0.0-31-generic  
运行时：**llama.cpp 自编译 Vulkan 后端**（不是 Ollama）  
模型：`OBLITERATUS/Ornith-1.5-9B-OBLITERATED`，基座 `ornith-ai/Ornith-1.5-9B`  
量化：`Q5_K_M`，6.19 GiB

> 这台机器没有用 Ollama。Radeon 760M 是 `gfx1103`，不在 ROCm 官方支持列表内，
> 所以改用 Mesa RADV 的 Vulkan 后端，仅监听回环地址。
> 四项测试的提示词、答案提取和评分代码与 Mac 部分一致
> （新增 `eval_gsm8k_llamacpp.py` / `eval_bfcl_llamacpp.py` / `eval_ifeval_llamacpp.py`，
> 其中 BFCL 与 IFEval 直接复用原有脚本的评分函数），因此**正确率可横向比较**；
> 但引擎不同，**耗时不可直接对比**。

## 模型来源说明

这**不是 Qwen 官方模型**，但确实是 Qwen 架构。基座 `ornith-ai/Ornith-1.5-9B`
的 `config.json` 里 `architectures` 是 `Qwen3_5ForConditionalGeneration`，
`model_type` 是 `qwen3_5`，32 层、每 4 层一个 full attention、其余为
linear attention——即 Qwen3.5 的混合注意力设计。

权重则来自 Ornith 自己的训练路线：Ornith-1.0 是在 **Qwen3.5 与 Gemma4** 基础上
做了继续预训练、中训与后训得到的，Ornith-1.5 又叠加了自我改进的强化学习循环。
所以本机跑的是「Qwen3.5 架构 + Ornith 权重 + OBLITERATUS 消融」的模型，
与 Qwen3.5-9B 不是同一组权重（Ornith 官方卡片也把 Qwen3.5-9B 单列一栏对比）。

## 采样设置（重要）

第一轮测试**直接套用了仓库惯例 `temperature=0`、且没有设置任何重复惩罚**——
这是本机端点的默认状态（`repeat_penalty=1.0`、`presence_penalty=0.0`、`dry=0.0`）。
而 Ornith 官方卡片推荐的是：

```text
temperature=1.0, top_p=0.95, top_k=20, min_p=0.0,
presence_penalty=1.5, repetition_penalty=1.0
```

这个差别直接造成了第一轮 IFEval 的失败模式（见下文）。**先按默认设置跑、事后才补
推荐设置的顺序是错误的**，应当先读卡片的推荐调用方式再开测。

## 部署结果

核显是统一内存架构，没有独立显存：

| 项 | 值 |
|---|---|
| UMA 显存划分 | 4.00 GiB |
| GTT（可映射的系统内存） | 9.41 GiB，即内存总量的一半 |
| llama.cpp 可用显存 | 13,730 MiB |
| 实际上下文 | 8192，KV cache 量化为 `q8_0` |
| 加载后占用 | 约 7 GB（权重 6.19 GiB + KV + 计算缓冲） |
| 处理器分配 | 100% GPU（Vulkan），无 CPU 分层卸载 |
| 模型加载耗时 | 约 2 秒（页缓存已热） |
| 磁盘下载量 | 6.19 GiB；`--hf-repo` 还会自动下载 0.86 GiB 视觉投影文件，本机用 `--no-mmproj` 跳过 |
| 解码吞吐 | 单流 11.6 tok/s |

需要额外装 `spirv-headers` 和 `glslc`，否则 llama.cpp 的 CMake 配置会因找不到
`SPIRV-Headers` 直接失败。

## 测试汇总

| 测试 | 仓库惯例 `temp=0` | **卡片推荐采样** |
|---|---:|---:|
| GSM8K 普通模式，前 10 题 | 4/10（连跑两次为 4 与 5） | **7/10**（15.6 秒，164.8 tokens） |
| GSM8K 思考模式，前 3 题 | 3/3（15.7 秒，169.3 tokens） | 未测 |
| BFCL v4 simple_python，前 20 题 | 16/20（5.6 秒，55.3 tokens） | **15/20**（9.9 秒，77.0 tokens） |
| IFEval 前 10 题 Strict | 3/10，9/18（93.9 秒，1071.6 tokens） | **4/10，11/18**（70.9 秒，802.6 tokens） |
| IFEval 前 10 题 Loose | 4/10，10/18 | 4/10，11/18 |
| IFEval + **开启思考** | **无法完成**（推理超出 4096 token） | 同左 |

### 与 Mac 各模型的同口径对比

| 模型（引擎） | GSM8K普通10 | GSM8K思考3 | BFCL20 | IFEval Strict题级 | IFEval Strict指令级 |
|---|---:|---:|---:|---:|---:|
| Qwen3 8B（Ollama/M3） | **10/10** | 1/3 | **16/20** | 8/10 | 16/18 |
| Qwen3.5 9B（Ollama/M3） | 2/10 | 1/3 | **16/20** | **10/10** | **18/18** |
| Qwen3.5 4B（Ollama/M3） | 4/10 | 1/3 | 15/20 | 7/10 | 15/18 |
| Qwen3.8 27B 官方权重（Ollama/M3） | 6/10 | **3/3** | **16/20** | **10/10** | **18/18** |
| Qwen3.8 27B Uncensored（Ollama/M3） | 5/10 | **3/3** | **16/20** | **10/10** | **18/18** |
| Gemma 4 E4B（Ollama/M3） | 6/10 | **3/3** | 15/20 | 6/10 | 13/18 |
| Nanbeige4.2 Q6（Ollama/M3） | 2/10 | 2/3 | 15/20 | 8/10 | 15/18 |
| **Ornith-1.5-9B-OBLITERATED（llama.cpp/AMD，卡片采样）** | **7/10** | **3/3** | **15/20** | **4/10** | **11/18** |

**一句话结论：按卡片推荐采样后，普通数学 7/10、工具调用 15/20 属中上游，
严格指令遵循 4/10 仍是全部被测模型里最差的。**

采样设置对结果影响极大：`temp=0` 下 GSM8K 只有 4–5/10 并出现退化重复，
换用卡片采样后升到 7/10。因此本表以卡片采样为准，`temp=0` 一列仅作对照。
与 abliterated Qwen3-8B 的同机同口径对比见
[AMD abliterated Qwen3-8B 测试](2026-09-19-amd-ryzen-7640hs-abliterated-qwen3-8b.md)。

## GSM8K

普通模式用官方前 10 题、输出上限 512。**同一套配置连跑两次得到 4/10 和 5/10**，
差异来自第 3、5、9 题（第 9 题一次答 0.5、一次答 45 并且答对）。即使
`temperature=0`，Vulkan 后端的浮点归约顺序也会让结果在两次运行间分叉，
所以 n=10 的差距只有 ±1 题的噪声量级，不能据此判断模型强弱。

失败多为接近答案的算术失误（目标 540 给出 180、目标 260 给出 240），
不是拒答或格式问题。

思考模式用同一批题的前 3 题、上限 1024，得到 3/3。第 3 题在普通模式下答成
`-10000`（目标 70000），开思考后答对——和 Mac 上其他模型一致。

## 工具调用：BFCL v4 simple_python 前 20 题

得到 **16/20**，与前 20 题并列第一的 Qwen3 8B / Qwen3.5 9B / 两个 27B 同分。
平均 5.6 秒、55.3 tokens，停止行为干脆（没有一次触顶）。

但第一次运行只有 15/20，原因**不是模型**：BFCL 的函数 schema 里用了 JSON Schema
不存在的类型 `"float"`，llama.cpp 会严格校验并直接返回 HTTP 500：

```text
JSON schema error at #/properties/interval/items: unrecognized type float
JSON schema error at #/properties/x_value: unrecognized type float
```

Ollama 容忍这个写法，llama.cpp 不容忍，所以这两题**在模型被问到之前就失败了**。
把 `float` 归一成 `number` 后回到 16/20。该修正只加在 llama.cpp 一侧，
原有 Ollama 脚本未改动。

其余失败是 `wrong_call`：调用了正确的函数但参数不符（例如多给了 `root_type`）。
按「请求阶段失败也算错」的口径，as-run 数字是 15/20。

## 严格指令遵循：IFEval 前 10 题

| 配置 | 题级 Strict | 指令级 Strict | 题级 Loose | 指令级 Loose | 截断 |
|---|---:|---:|---:|---:|---:|
| 默认 `temp=0`，无重复惩罚 | 3/10 | 9/18 | 4/10 | 10/18 | 4/10 |
| **卡片推荐采样** | **4/10** | **11/18** | 4/10 | 11/18 | 2/10 |
| 卡片推荐采样 + 开启思考 | — | — | — | — | — |

### 第一轮为什么差：解码循环，不是能力

默认设置下 10 题有 4 题在 2048 token 上限处被截断，第 1 题的回答尾部是典型的
退化重复：

```text
...became legendary. The land prospered. He created institutions. History
remembers him. The name became famous. The land thrived. He created a new
order. History
```

`temperature=0`（贪心）叠加 `presence_penalty=0.0`、`repeat_penalty=1.0`、
`dry=0.0`——即没有任何机制抑制重复——正是这类循环的成因。换成卡片推荐的
`presence_penalty=1.5` 后，10 题全部自然停止（只剩 2 题触顶），
平均输出从 1071 降到 803 tokens。

### 但换成推荐采样后仍然很差

分数只从 3/10、9/18 升到 **4/10、11/18**，仍然是全部被测模型里最低的
（次低的 Gemma 4 E4B 是 6/10、13/18）。而且这是在**同为关闭思考**的匹配条件下
与 Qwen3.5 9B（10/10、18/18，平均仅 284 tokens）比较的。

所以「第一轮成绩纯属配置问题」这个解释**只对了一半**：配置确实造成了
重复循环并被修复，但修复后模型在严格格式约束上依然明显弱于同规模的
Qwen3.5 9B。这是该模型一个**未被官方卡片披露**的弱项，而不是虚假宣传。

### 思考模式在本机不可用

官方卡片说明 Ornith-1.5-9B 是 reasoning model，助手回合默认以 `<think>` 开头，
推荐的 serving 配方使用 128K–256K 上下文和最高 131072 输出预算。
在本机开启思考后实测：**第 1 题就把 4096 token 全部用在 reasoning_content 上**
（推理文本 10453 字符），`content` 为空字符串、`finish_reason=length`，
单题耗时 360 秒仍未产出答案。

按 11.6 tok/s 推算，每题仅推理就需要 6 分钟以上且仍然截断，因此在这台
18 GiB、8192 上下文的核显机器上，**该模型的思考模式没有实用价值**，
本次也无法给出开启思考后的 IFEval 分数。官方数字所依赖的运行条件
（大上下文 + 大输出预算）超出了这台机器的能力。

## 综合判断

就模型本身：**工具调用（16/20）与思考数学（3/3）都是并列第一**，普通数学中游，
但**严格指令遵循明显偏弱**，且**原生思考模式在这台机器上跑不动**。

关于「是否虚假宣传」：不支持这个结论。理由有三：

1. 官方卡片公布的基准（Terminal-Bench 2.1、SWE-bench Verified/Pro/Multilingual、
   NL2Repo、SWE Atlas、HLE、GPQA Diamond、MCP-Atlas、Toolathlon、WideSearch、
   BrowseComp、ClawEval）**与本仓库测的四项完全不重叠**，我们无法证伪其数字。
2. 卡片写明了 5 次平均、命名 harness、解码参数与反作弊措施，也**主动披露了
   局限**（MMLU −4pp、function calling 部分退化、低量化更易含糊），
   不是虚标卡片的常见形态。
3. 唯一可对照的能力轴——工具调用——我们测出 16/20 并列第一，与其强调
   agentic 能力一致；消融主张也被我们另外测到的拒答结果支持。

正确的表述是：**该模型的强项与卡片一致，但它在卡片未报告的严格格式约束上偏弱，
且它的原生思考模式在 18 GiB 核显设备上不可用。** 这是能力画像不完整与硬件不匹配，
不是虚假宣传。

建议用途：

- 单轮工具调用 / 函数调用类任务（16/20）；
- 关闭思考的普通问答与内容生成；
- uncensored/abliterated 微调行为研究。

不建议作为：

- 严格格式与约束类任务（IFEval 4/10，全部被测模型中最低）；
- 需要原生思考的推理任务（本机不可用）；
- 低延迟聊天默认模型。

## 局限

- GSM8K 10 题、思考 3 题、BFCL 20 题、IFEval 10 题，样本很小；GSM8K 已实测
  同配置两次跑出 4/10 与 5/10，说明 ±1 题属噪声。
- 只跑了 BFCL `simple_python`，未跑 multiple/parallel/irrelevance/multi_turn_base。
- IFEval 只测到「关闭思考」；开启思考在本机无法完成，两版数字都未覆盖该模式。
- 只有 Q5_K_M 一个量化，没有跑未 abliterated 的基座做对照，因此没有 KL 散度。
- BFCL 的 `float`→`number` 归一化是本地为绕开 llama.cpp 严格校验而加的，
  属于引擎兼容处理，不是 BFCL 官方口径。
- 第一轮 IFEval 使用了不合适的采样设置，已保留原始结果与修正后结果并列，
  不应只引用其中一版。
- 本机另有安全侧结果（AdvBench / HarmBench 拒答率与规避行为），不在本仓库口径内，
  记录在 OpenClaw 集群仓库的 `docs/evals/2026-09-19-oc-node-02-abliterated-llm-eval.md`。
