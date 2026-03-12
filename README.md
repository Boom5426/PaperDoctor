# PaperDoctor

**PaperDoctor 是一个用于科研论文审阅与修改的 AI Agent。** 它会先 **诊断论文中的逻辑问题**，再生成 **可执行的修改建议**。

就像医生：

```
论文
 ↓
诊断逻辑问题
 ↓
开出修改方案
```

---

# 为什么需要 PaperDoctor

目前大多数 AI 写作工具的流程是：

```
论文 → Prompt → 修改建议
```

这通常会产生：

* 泛泛建议
* 无法定位具体问题
* 缺乏证据链分析

PaperDoctor 引入 **诊断层 (Diagnosis Layer)**：

```
论文
 ↓
结构解析
 ↓
逻辑诊断
 ↓
修改规划
 ↓
Revision Report
```

这样生成的建议：

* 可定位
* 有证据
* 可执行

---

# 核心能力

PaperDoctor 的核心是一个 **Agent Pipeline**。

---

## 1 文档解析

解析 `.docx` 论文：

* section
* paragraph
* figure reference

输出：

```
paper_raw.json
```

---

## 2 章节角色识别

识别段落在论文中的角色：

* Background
* Gap Identification
* Contribution
* Result Interpretation
* Discussion

避免结构错位。

---

## 3 Claim-Evidence Mapping

识别：

```
Claim → Evidence
```

检测问题：

* Claim 没有证据
* Claim 过度
* Evidence 不匹配

---

## 4 逻辑漏洞诊断

PaperDoctor 会检测：

* Claim-Evidence mismatch
* 叙事链断裂
* 段落角色错位
* 期刊适配问题

---

## 5 Revision Planner

生成结构化修改建议：

```
Current Problem
Why It Matters
Source Span
How To Fix
Example Rewrite
```

---

# 示例

原始段落：

> Organoids have emerged as powerful tools for modeling clinical responses.

---

诊断结果：

```
Role: FIELD_CONTEXT
Claim: organoids are superior models
Evidence: none provided
Logical Issue:
lack of quantitative justification
```

---

修改建议：

**Problem**

段落声称类器官模型更优，但没有定量证据。

**Fix**

增加文献或数据支持。

**Example Rewrite**

> Organoids have emerged as powerful models for studying clinical responses, offering higher physiological fidelity than traditional cell lines. Recent studies report improved predictive accuracy in drug response modeling.

---

# 系统架构

```
Input Paper (.docx)

        │
        ▼

Document Parsing

        │
        ▼

Logic Diagnosis
(section roles
claim-evidence)

        │
        ▼

Revision Planner

        │
        ▼

Revision Report
```

---

# Demo

运行：

```
python run_agent.py examples/sample_paper.docx
```

输出：

```
logic_map.json
revision_report.md
```

---

# 项目目标

PaperDoctor 探索一个问题：

**如何让 AI 对长文档进行结构化推理，而不是一次性生成文本。**

核心方法：

> 将文档理解转化为显式中间状态。

---

# Roadmap

### v0.1

论文 revision agent

* docx 支持
* logic diagnosis
* revision report

---

### v0.2

增强能力：

* figure / table evidence mapping
* citation analysis

---

### v0.3

扩展到：

* grant proposal
* technical report
* whitepaper

---

# 4️⃣ Agent Pipeline（面试官会看的）

你项目真正的技术点是：

```
paper
 ↓
preprocessing
 ↓
logic_map
 ↓
planner
 ↓
report
```

其中：

logic_map 是核心 artifact。

示例：

```json
{
  "section": "Introduction",
  "role": "Gap Identification",
  "claim": "...",
  "evidence": "...",
  "vulnerability": "...",
  "priority": 1
}
```

---

# 5️⃣ 第一个 Demo（非常关键）

建议做一个：

**Before vs After**

比如：

Baseline GPT：

```
Strengthen the logic of this paragraph.
```

PaperDoctor：

```
Problem:
Claim lacks quantitative evidence.

Fix:
Add statistics comparing organoids vs cell lines.

Example rewrite:
...
```

这种 demo 会让 repo 更容易 star。

---

