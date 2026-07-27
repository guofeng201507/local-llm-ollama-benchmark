# 2026-07-26 BFCL 工具调用测试总结

## 测试集

本轮使用 [Berkeley Function Calling Leaderboard（BFCL）](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard)
v4 的 `simple_python` 前 20 题。

BFCL 是 UC Berkeley 开源的函数调用评测，覆盖单函数、多函数、并行调用、
多轮调用、无关工具和可执行性等类别。本轮只是最基础的单函数子集冒烟测试，
不代表 BFCL 官方排行榜成绩。

## 方法

本地模型通过 Ollama 原生 `/api/chat` 接口接收 `tools`：

- `think=false`
- 温度 0
- 上下文 4096
- 最大输出 256 Token
- 不实际执行工具
- 严格比较函数名和参数
- 缺少必需参数、参数值错误、额外参数或未调用工具均判错

BFCL 数据中的 JSON Schema `type: "dict"` 在发送给 Ollama 前转换为标准的
`type: "object"`，不改变函数名、参数和标准答案。

GPT-5.6 Sol 无法在当前Codex代理环境中动态注册这20个BFCL函数，因此采用
文本Schema生成结构化调用，只能作为函数选择和参数生成参考，不能与Ollama
原生工具协议完全等价。

## 结果

| 模型 | 原生工具协议 | 正确率 | 平均耗时 | 平均输出 |
|---|---|---:|---:|---:|
| Qwen3 8B | 是 | **16/20** | **9.70 秒** | 32.25 Token |
| Qwen3.5 9B | 是 | **16/20** | 27.42 秒 | 46.25 Token |
| Gemma 4 E4B | 是 | 15/20 | 12.30 秒 | **21.65 Token** |
| Qwen3.5 4B | 是 | 15/20 | 31.09 秒 | 50.05 Token |
| Nanbeige4.2 Q6 | 是 | 15/20 | 21.40 秒 | 69.95 Token |
| GPT-5.6 Sol | 否，文本Schema参考 | 15/20 | 不可比 | 不可比 |

## 观察

### Qwen3 8B

正确率并列第一，同时是本地模型中最快的，延续了GSM8K普通模式中表现出的
良好可用性。前14题全部正确，后段涉及函数字符串表示和严格布尔参数时开始
出错。

### Qwen3.5 9B

正确率同为16/20，但平均耗时约为Qwen3 8B的2.8倍。冷启动前几题尤其慢，
首题约61秒；预热后多数题下降到约10–28秒。它在工具调用上明显好于之前的
数学普通模式，但综合效率仍不如Qwen3 8B。

### Gemma 4 E4B

得到15/20，平均输出最少。整体速度仅次于Qwen3 8B，函数调用比较干净。
主要失败仍集中在严格参数表示，而不是完全选错函数。

### Qwen3.5 4B

得到15/20，但平均耗时最高。两题没有产生工具调用，另外几题参数表示错误。
在本机上没有体现出小参数模型应有的速度优势。

### Nanbeige4.2 Q6

虽然Ollama模型能力清单只突出completion，Nanbeige专用分支实际上能够解析
`tools`并返回原生工具调用，得到15/20。两题发生HTTP API错误，其他失败题
主要是参数问题。它的工具调用表现明显好于此前2/10的数学普通模式，但延迟
和输出长度较高。

### GPT-5.6 Sol参考

得到15/20。5个失败项都是严格参数表示问题：

- 使用数学写法`x^2`，而标准答案只接受Python形式`x**2`或等价lambda。
- `get_prime_factors`的`formatted`选择了`false`，标准答案接受`true`或省略。

它正确选择了全部20个函数；该成绩反映严格参数匹配，但不是原生工具协议
成功率。

## 结论

这20道基础工具题的区分度有限，但已经能说明：

1. 本地模型确实可以通过Ollama原生工具协议工作。
2. Qwen3 8B仍是当前准确率、速度和资源之间最均衡的选择。
3. 参数量更大的Qwen3.5 9B没有带来更好的工具调用准确率。
4. 数学问答表现差不代表工具调用一定差；Nanbeige是最明显的例子。
5. 严格的参数序列化和默认值处理是主要失败来源。

下一轮应增加更有区分度的BFCL类别：

- `multiple`：在多个函数中选择正确函数
- `parallel`：一次生成多个并行调用
- `parallel_multiple`：多函数并行调用
- `irrelevance`：不该调用工具时保持不调用
- `multi_turn_base`：多轮工具调用和状态维护

## 2026-07-27 扩展类别结果

已用相同的固定前5题（`offset=0, limit=5`）测试上述五个类别。每个模型共
25个场景；`multi_turn_base`的5个场景合计18轮。该样本用于本机工具代理
选型，仍不是BFCL官方排行榜成绩。

单轮类别按无序调用集合严格评分：调用数量、函数名、参数名和值都必须匹配。
`irrelevance`要求零工具调用。多轮测试逐轮加入用户消息，并为模型的调用返回
固定的成功工具结果；整段场景只有每轮都正确才通过，同时单独报告正确轮数。
这种确定性合成反馈便于模型间比较，但不执行BFCL官方的状态模拟器。

| 模型 | multiple | parallel | parallel_multiple | irrelevance | multi_turn_base | 合计 |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3 8B | **5/5** | **5/5** | **4/5** | **5/5** | 0/5（5/18轮） | **19/25** |
| Gemma 4 E4B | **5/5** | **5/5** | **4/5** | **5/5** | 0/5（4/18轮） | **19/25** |
| Qwen3.5 9B | 4/5 | 4/5 | 3/5 | **5/5** | 0/5（3/18轮） | 16/25 |
| Nanbeige4.2 3B Q6 | 2/5 | 2/5 | 1/5 | 0/5 | 0/5（1/6已执行轮） | 5/25 |

| 模型 | multiple | parallel | parallel_multiple | irrelevance | multi_turn_base |
|---|---:|---:|---:|---:|---:|
| Qwen3 8B | 4.56秒 | 5.89秒 | 5.25秒 | **10.82秒** | **31.90秒** |
| Gemma 4 E4B | **3.62秒** | **3.66秒** | **5.02秒** | 20.81秒 | 35.11秒 |
| Qwen3.5 9B | 16.49秒 | 21.62秒 | 21.31秒 | 29.48秒 | 102.71秒 |
| Nanbeige4.2 3B Q6 | 4.72秒* | 17.48秒* | 11.36秒* | 不可用 | 28.97秒* |

\* Nanbeige延迟只累计成功到达推理的请求，不能和其他模型直接比较。其专用
Ollama分支在4096上下文下有16/25个场景因工具Schema和提示超过上下文而返回
HTTP错误；这反映当前部署组合的工具代理可用性，不应解释为纯模型能力。

### 工具代理建议

**首选Qwen3 8B。** 它与Gemma同为19/25，但多轮正确轮数略高（5/18对
4/18），无关请求判断快约一倍，且此前`simple_python`也是并列第一。它是
当前准确率、覆盖面、延迟和部署稳定性最均衡的本地工具代理。

**Gemma 4 E4B适合作为单轮低延迟备选。** 它在`multiple`和`parallel`最快，
且单轮准确率与Qwen3 8B相同；如果工作流主要是一次选择或并行调用工具，可以
优先考虑Gemma。

**不要把本轮任何模型用于无人监督的多轮写操作。** 四个模型在严格整段评分
中均为0/5。实际代理应逐轮校验函数和参数、限制可写工具、保留人工确认，并在
错误时停止，而不是继续执行后续动作。

Qwen3.5 9B更慢且单轮准确率更低，没有体现出9B规模优势。Nanbeige当前专用
服务的上下文限制会直接拒绝较大的工具集合，不建议作为通用工具代理；若继续
研究，应先用更大`num_ctx`重新验证服务稳定性。

## 复现

下载BFCL：

```bash
git clone --depth 1 https://github.com/ShishirPatil/gorilla.git eval-data/gorilla
```

运行示例：

```bash
.venv-eval/bin/python -u eval_bfcl_ollama.py \
  --model qwen3:8b \
  --label qwen3-8b \
  --limit 20
```

逐题结果位于：

```text
eval-results/tool-calling/
```

扩展运行示例：

```bash
python3 -u eval_bfcl_ollama.py \
  --model qwen3:8b \
  --label qwen3-8b \
  --category parallel_multiple \
  --limit 5
```

聚合数据保存于
`eval-results/tool-calling/bfcl-v4-next-categories-summary-n5-o0.json`，
各模型、各类别的JSONL保留逐场景和逐轮调用。
