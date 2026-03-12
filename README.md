<p align="center">
  <img src="PaperDoctor.png" width="800">
</p>

**PaperDoctor** 是一个面向科研论文的 **`paper diagnosis agent`**，目标不是直接帮你“润色句子”，而是先把论文的主线逻辑、claim-evidence 关系、storyline 风险和 revision priorities 结构化地拆出来，再输出可执行修改建议。

当前项目的主打场景是：

- Nature-family / Nature 系列期刊质量提升
- 投稿前逻辑诊断与修改规划
- 可运行、可展示、可复现的最小开源工作流

PaperDoctor 当前不是一个普通 paper editor。它更像一个投稿前诊断器：

- 先解析论文结构
- 再识别段落角色、claim、evidence
- 再抽取整篇论文主线
- 最后输出 revision report

## 为什么需要它

很多论文工具只做润色、改写或摘要，但真正影响高水平投稿结果的，往往是这些问题：

- 研究问题讲得不够清楚
- main gap 没有被明确说出来
- contribution 不够锋利
- claim 和 evidence 对不上
- validation 不够扎实
- Discussion 没有把 significance 讲出来

PaperDoctor 的目标，就是把这些问题在真正修改之前先诊断出来。

## 当前定位

当前优先场景：- Nature-family paper quality improvement

这不代表项目架构只能服务 Nature-family。当前只是先聚焦一个最容易展示价值、最容易形成产品定位的场景。底层 pipeline 仍然可以扩展到其他期刊、其他论文类型或更长文档。

## 核心工作流

当前最小闭环流程如下：

`docx -> paper_raw.json -> section_roles.json -> claims.json -> evidence_map.json -> nature_quality_rubric.json -> logic_map.json -> issue_clusters.json -> storyline.json -> journal_profile.json -> revision_report.md`

当前 workflow 已升级为 `artifact-first`：

- 原始 `.docx` 只在 preprocessing 阶段读取一次
- 后续分析默认复用已生成的中间产物
- 特别适合长论文反复分析，避免每次都重新读取全文、重复消耗 token
- 运行时会输出清晰的阶段日志，告诉用户当前做到哪一步

对应步骤：

1. 输入论文 `.docx`
2. 文档解析，生成基础结构化内容
3. 段落角色识别
4. claim 提取
5. evidence 映射
6. 使用 Nature-family 质量 rubric 做逻辑诊断
7. 将真实问题合并为 paper-level issue clusters
8. 提取整篇论文 storyline / core argument
9. 输出 revision report

## Artifact-First Workflow

PaperDoctor 现在采用“单次读取、持续复用”的 artifact-first 工作流。

核心原则：

- `.docx` 只在 `parse_docx` 阶段读取一次
- 如果论文内容未变，优先复用已有 `paper_raw.json`
- 后续模块统一消费中间产物，而不是重复读取整篇原文

当前会优先复用这些 artifact：

- `paper_raw.json`
- `section_roles.json`
- `claims.json`
- `evidence_map.json`
- `nature_quality_rubric.json`
- `logic_map.json`
- `storyline.json`
- `journal_profile.json`
- `revision_report.md`

同时会维护：

- `outputs/session_manifest.json`

它用于记录：

- `paper_id`
- `source_docx`
- `doc_hash`
- 已生成的 artifact
- 每个 artifact 的生成时间和复用状态

这套机制的意义是：

- 长论文只需要 preprocessing 一次
- 后续改 scope 或重复运行时，尽量基于已有中间状态继续分析
- 减少重复 token 消耗，尤其适合 VC2O 这类长论文

## 安装方式

### 1. 克隆项目

```bash
git clone https://github.com/Boom5426/PaperDoctor.git
cd PaperDoctor
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置 API

PaperDoctor 提供了统一的 LLM 配置层，兼容 OpenAI 风格接口，并支持当前常见的 OpenAI-compatible API relay。

当前环境变量：

- `PAPERDOCTOR_API_KEY`
- `PAPERDOCTOR_BASE_URL`
- `PAPERDOCTOR_MODEL`
- `PAPERDOCTOR_MAX_TOKENS`
- `PAPERDOCTOR_TIMEOUT`

### 1. 复制环境文件

```bash
cp .env.example .env
```

### 2. 填写 `.env`

`.env.example` 默认内容已经准备好：

```env
PAPERDOCTOR_API_KEY=your_api_key_here
PAPERDOCTOR_BASE_URL=https://vip.yi-zhan.top/v1
PAPERDOCTOR_MODEL=gemini-3-flash-preview
PAPERDOCTOR_MAX_TOKENS=40000
PAPERDOCTOR_TIMEOUT=600
```

注意：

- 不要把真实 `api_key` 写进代码
- 不要把真实 `api_key` 提交到 Git
- `.env` 已经被 `.gitignore` 忽略

## 运行 Demo

最简单的运行方式：

```bash
python run_agent.py examples/sample_paper.docx
```

也可以显式传入轻量 journal profile：

```bash
python run_agent.py examples/sample_paper.docx --journal "Nature Methods"
```

也可以只分析局部范围：

```bash
python run_agent.py examples/sample_paper.docx --scope intro
python run_agent.py examples/sample_paper.docx --scope results
```

如果想看更详细的 artifact 复用与 scope 统计：

```bash
python run_agent.py examples/sample_paper.docx --verbose
```

如果要强制重算当前 scope 对应的 artifact：

```bash
python run_agent.py examples/sample_paper.docx --refresh
python run_agent.py examples/sample_paper.docx --scope intro --refresh
```

注意：

- 当前 `journal` 参数只是轻量 profile 输入
- 项目定位仍然是“提升到 Nature-family 质量”
- 并没有实现复杂子刊打分器或 issue weighting
- 默认会优先复用缓存 artifact
- 当 `scope != full` 时，输出文件会带 scope 前缀，例如 `intro_logic_map.json`
- 命中缓存时，运行日志会显示 `reuse`
- 发生重算时，运行日志会显示 `recompute`

## 输出说明

运行后，至少会生成以下文件：

- `outputs/paper_raw.json`
  - 论文原始结构化内容
  - section / paragraph / references

- `outputs/section_roles.json`
  - 每个段落的角色判断
  - 例如 `Background`、`Gap Identification`、`Contribution`

- `outputs/claims.json`
  - 每个段落是否有明确 claim
  - claim 文本及状态

- `outputs/evidence_map.json`
  - 每个段落的 evidence 支撑情况
  - citation / figure-table / explicit result

- `outputs/nature_quality_rubric.json`
  - 当前统一的 Nature-family 质量 rubric

- `outputs/logic_map.json`
  - 逻辑诊断主结果
  - 只保留真实问题，不再按 paragraph 机械地产生 issue

- `outputs/issue_clusters.json`
  - 论文级问题簇
  - 将相关 issue 按 theme / claim / section 合并
  - 是 `storyline` 和 `revision_report` 的直接上游

- `outputs/storyline.json`
  - 整篇论文的轻量主线 artifact
  - 包括：
    - `main_problem`
    - `main_gap`
    - `core_contribution`
    - `supporting_results`
    - `main_risks`
    - `significance_risk`

- `outputs/journal_profile.json`
  - 当前轻量 Nature-family profile

- `outputs/revision_report.md`
  - 最终给作者看的诊断与修改报告

- `outputs/session_manifest.json`
  - 当前论文 session 的 artifact 清单
  - 用于判断哪些结果可以 reuse，哪些需要 recompute

## 项目结构

```text
PaperDoctor/
├── paperdoctor/
│   ├── llm/
│   │   ├── __init__.py
│   │   └── client.py
│   ├── agent.py
│   └── pipeline.py
├── skills/
│   ├── parse_docx.py
│   ├── section_role_annotator.py
│   ├── claim_extractor.py
│   ├── evidence_mapper.py
│   ├── nature_quality_rubric.py
│   ├── storyline_builder.py
│   ├── logic_mapper.py
│   ├── journal_adapter.py
│   └── revision_planner.py
├── schemas/
├── examples/
├── outputs/
├── docs/
│   ├── architecture.md
│   └── quickstart.md
├── .env.example
├── .gitignore
├── requirements.txt
└── run_agent.py
```

关键说明：

- `paperdoctor/llm/client.py`
  - 统一读取 API 配置
  - 封装 OpenAI 风格调用

- `paperdoctor/pipeline.py`
  - 串联整个最小工作流

- `skills/`
  - 论文诊断的核心模块

- `examples/sample_paper.docx`
  - 可直接运行的 demo 输入

- `docs/quickstart.md`
  - 更偏操作手册的快速上手说明

## 当前 LLM 接入状态

当前项目已经接入统一 LLM 配置层，但核心 pipeline 仍然以稳定的启发式实现为主。

这意味着：

- 你现在就可以 clone 后直接跑通 demo
- API 配置已经统一，不会散落在各个 skill 里
- 后续把某个 skill 升级成 LLM 驱动时，可以直接复用 `paperdoctor.llm.client`
- 当前已真实接入的模块包括：
  - `skills/claim_extractor.py`
  - `skills/revision_planner.py`
- 如果 `PAPERDOCTOR_API_KEY` 已配置，claim extraction 和 revision suggestions 会优先使用 LLM 增强
- 如果未配置或请求失败，会自动回退到本地 heuristic 版本

## 当前限制

当前版本明确不做：

- PDF / LaTeX 支持
- Web UI
- rebuttal / cover letter generation
- 多 agent orchestration
- 长期记忆

当前已知限制：

- 目前只支持 `.docx`
- 当前以 Nature-family 质量诊断为主
- 当前 LLM client 已接入，但主要分析逻辑仍以 heuristic-first 为主
- 当前 cache 策略是最小可用版本，重点解决“长论文重复读取和重复分析”的问题

## 快速排查

常见问题请直接看：

- `docs/quickstart.md`

其中包含：

- API key 未配置
- base_url 无法连接
- docx 文件不存在
- outputs 未生成

## 适合如何使用

如果你要用这个项目做 GitHub 展示，建议最少展示这三样：

- `examples/sample_paper.docx`
- `outputs/storyline.json`
- `outputs/revision_report.md`

它们最能体现 PaperDoctor 的差异点：

- 不是只做句子润色
- 而是先诊断整篇论文主线和逻辑质量
