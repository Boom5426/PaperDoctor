# PaperDoctor

> 一个用于 **诊断科研论文逻辑问题并生成可执行修改方案的 AI Agent**

写论文最难的，从来不是语法。而是 **逻辑**。

- Introduction 是否真正建立了研究 gap？
- 每个 Claim 是否有足够证据支撑？
- Results 是否真的支持核心结论？
- 论文叙事是否符合目标期刊的逻辑结构？

很多 AI 写作工具可以 **润色文字**。

但很少有工具能 **诊断论文的逻辑问题**。

**PaperDoctor 的目标不是“改写论文”，而是像医生一样诊断论文。**

---

# 为什么需要 PaperDoctor

目前大多数 AI 论文修改工具的流程是：论文 → Prompt → 修改建议


这种方式常常产生：

- 泛泛的建议  
- 不知道具体问题在哪  
- 建议与论文结构脱节  
- 甚至产生幻觉式批评  

例如：

> “建议增强逻辑。”

这几乎没有帮助。

因为它没有说明：

- **哪一段有问题**
- **为什么这是问题**
- **应该怎么修改**

---

# PaperDoctor 的思路

PaperDoctor 把论文当成一个 **需要诊断的系统**。

在提出修改建议之前，它会先进行 **逻辑诊断**。

**整体流程：论文 → 文档解析 → 逻辑诊断 → 修改规划 → Revision Report**


核心思想：

> 在 AI 生成建议之前，先构建 **结构化推理状态**。

---

# 核心概念：Logic Map（逻辑地图）

PaperDoctor 会把论文拆解成 **逻辑单元**。

每个段落都会被标注：

- 段落角色
- 作者 Claim
- 支撑 Evidence
- 逻辑漏洞

示例：

```json
{
  "section": "Introduction",
  "role": "Gap Identification",
  "claim": "Existing virtual cell models fail to generalize to organoid data.",
  "evidence": "None",
  "logical_vulnerability": "该 Claim 假设 batch effect 是唯一问题，但未讨论 biological drift。"
}





