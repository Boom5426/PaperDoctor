# Project: PaperDoctor

PaperDoctor 是一个用于 **诊断科研论文逻辑问题并生成可执行修改方案的 AI Agent**。

项目目标不是简单的论文润色，而是构建一个 **具有明确推理结构的 Agent Pipeline**，用于分析论文逻辑并生成修改建议。

核心思想：

> 在 AI 修改论文之前，先进行结构化逻辑诊断。

---

# 项目核心目标

实现一个多阶段 Agent 系统，用于：

1. 解析论文结构
2. 识别段落在论文中的角色
3. 提取 Claim
4. 查找 Evidence
5. 发现逻辑漏洞
6. 生成可执行修改建议

系统必须生成中间推理状态，而不是直接生成修改文本。

---

# Agent Pipeline

系统流程如下：

Paper (.docx)
↓
Document Parsing
↓
Logic Mapping
↓
Claim-Evidence Analysis
↓
Revision Planning
↓
Revision Report

---

# 核心模块

需要实现以下模块：

## 1 preprocessing

输入：

论文 docx

功能：

- 提取 section
- 提取 paragraph
- 识别 figure / table reference

输出：

paper_raw.json

结构示例：

{
  "sections": [
    {
      "title": "Introduction",
      "paragraphs": [...]
    }
  ]
}

---

## 2 section_role_annotator

识别段落在论文中的角色，例如：

- Background
- Field Context
- Gap Identification
- Contribution
- Result Interpretation
- Discussion

输出：

{
  "paragraph_id": "...",
  "role": "Gap Identification"
}

---

## 3 claim_extractor

从段落中提取作者的 Claim。

输出：

{
  "paragraph_id": "...",
  "claim": "..."
}

---

## 4 evidence_mapper

检测 Claim 是否有 Evidence。

Evidence 包括：

- figure
- table
- experiment result
- citation

输出：

{
  "claim": "...",
  "evidence": "...",
  "evidence_type": "figure | citation | result"
}

---

## 5 logic_mapper

构建 Logic Map：

{
  "section": "...",
  "role": "...",
  "claim": "...",
  "evidence": "...",
  "logical_vulnerability": "...",
  "priority": 1
}

检测：

- Claim-Evidence mismatch
- 段落角色错误
- 叙事链断裂

---

## 6 revision_planner

根据 Logic Map 生成修改建议。

输出格式：

{
  "problem": "...",
  "why_it_matters": "...",
  "source_span": "...",
  "how_to_fix": "...",
  "example_rewrite": "..."
}

---

# 项目结构

项目结构如下：

paperdoctor/

paperdoctor/
agent.py
pipeline.py

skills/
parse_docx.py
section_role_annotator.py
claim_extractor.py
evidence_mapper.py
logic_mapper.py
revision_planner.py

schemas/
logic_map_schema.json
revision_schema.json

examples/
sample_paper.docx

outputs/
logic_map.json
revision_report.md

docs/
architecture.md

---

# 技术要求

语言：

Python

推荐库：

- python-docx
- pydantic
- openai / llm client
- networkx（可选）

代码必须：

- 模块化
- 每个模块可单独运行
- 支持 CLI 调用

---

# CLI 示例

python run_agent.py examples/sample_paper.docx

输出：

logic_map.json
revision_report.md

---

# Demo目标

示例输入：

一篇 research paper docx。

输出：

1 logic_map.json  
2 revision_report.md  

报告必须包含：

Current Problem  
Why It Matters  
How To Fix  
Example Rewrite

---

# 项目愿景

PaperDoctor 探索一个核心问题：

如何让 LLM 对长文档进行结构化推理，而不是一次性生成文本。

核心方法：

显式推理状态（Logic Map）。

---

# 第一阶段目标

实现：

- docx parsing
- logic map
- revision report

保证整个 pipeline 可以跑通。

---

# 未来扩展

- citation analysis
- figure / table evidence mapping
- reviewer simulation
- grant proposal analysis