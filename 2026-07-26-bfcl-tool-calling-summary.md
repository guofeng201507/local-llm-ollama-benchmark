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
