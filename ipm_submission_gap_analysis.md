# IPM 投稿差距分析报告

## 审阅范围
- 论文：`paper/ipm_submission/final_package/manuscript.pdf`（16 页）
- 项目代码：`src/fma/` 全模块
- 治理文件：`AGENTS.md`、`claim_registry.md`、`submission_lock_audit.md`、`submission_readiness_audit.md`
- 投稿包：`final_package/`（PDF、DOCX、LaTeX source、graphical abstract）

---

## 1. 执行摘要：总体判断

**论文主体已具备投稿条件**，但存在 **1 个中等风险（期刊 scope 匹配）** 和 **2 个低风险项（代码未实现模块、DOCX 渲染未验证）**。

| 维度 | 状态 | 说明 |
|------|------|------|
| 论文内容完整性 | ✅ 满足 | 16 页，结构完整（Intro → Related Work → Method → Eval → Limitations → Demo → Conclusion），claim-bounded 叙事严格 |
| 科学治理一致性 | ✅ 满足 | 论文措辞与 `claim_registry.md` 完全一致，无越界声明 |
| 项目代码核心功能 | ✅ 满足 | SC-FMA 核心（calibration、graph、ciu、baselines、ranking、eval）全部实现并通过测试 |
| 项目代码计划模块 | ⚠️ 差距 | `conditional/`、`matching/`、`dr/` 三个目录不存在（AGENTS.md 2.2 标记为 NOT YET IMPLEMENTED） |
| 投稿包格式 | ✅ 基本满足 | 除 DOCX 本地渲染（缺 LibreOffice）外，其余 format checklist 全部打勾 |
| 期刊 scope 匹配 | ⚠️ 风险 | 需确认 IPM 对"AI/ML 方法论文"的接受度；封面信已做知识密集型信息处理 framing，但属方法论论文而非传统信息检索 |

---

## 2. 论文与项目证据一致性 ✅

论文中的每一条实证声明均可在治理文件中找到对应边界：

| 论文声明 | 项目证据 | 治理状态 |
|----------|----------|----------|
| "QP improves Spearman from 0.483 (raw CIU) to 0.608" | 合成基准 200 traces, 1,027 steps, seed 42 | `M_SCFMA_CALIBRATION` supported |
| "w_struct achieves Spearman 0.611 on PRM800K" | v3.6 locked hash split, 4,417 samples, 34,219 steps | `M_STEP_RANKING` supported |
| "Ridge preserves w_struct at 0.604" | v3.6 同一路由 | `M_STEP_RANKING` supported |
| "Frozen PRM baseline 0.252, context only" | v3.8 locked split | `M_BASELINE_COMPARISON_CONTEXT_ONLY` stratum_dependent |
| "GSM8K/HotpotQA replay routes failed" | v2/v2.1/v2.2/v3/v3.1 全部失败归档 | `failed_validation` / `pilot_blocked` |
| "No downstream PRM training claim" | v2.1 mini filtering 失败；无 PRM 训练实验 | `F_PRM_TRAINING` future_validation |

**结论**：论文没有越界声明，负面结果被透明保留，与 `claim_registry.md` 完全一致。

---

## 3. 项目代码完整性 ⚠️

### 3.1 已实现的核心模块（与论文直接相关）

| 模块 | 路径 | 论文对应 | 状态 |
|------|------|----------|------|
| SCU 校准优化器 | `src/fma/calibration/optimizer.py` | Eq. 1, Theorem 3.1 | ✅ 实现 + 测试通过 |
| 图构建与诊断 | `src/fma/graph/` | Section 3.2 结构必要性、冗余、瓶颈 | ✅ 实现 + 测试通过 |
| CIU 估计 | `src/fma/ciu/estimator.py` | Section 4.1 合成基准 | ✅ 实现 + 测试通过 |
| 基线方法 | `src/fma/baselines/` | Table 2 所有基线 | ✅ 实现 + 测试通过 |
| 排名评估 | `src/fma/ranking/` | Spearman/NDCG/统计检验 | ✅ 实现 + 测试通过 |
| PRM 冻结评分 | `src/fma/prm/` | v3.8 frozen PRM 比较 | ✅ 实现 + 测试通过 |
| 数据加载 | `src/fma/data/` | PRM800K/GSM8K/ProcessBench | ✅ 实现 + 测试通过 |
| 可视化 | `src/fma/visualization/` | Figure 1–3 | ✅ 实现 |
| 审计优先化 | `src/fma/eval/prm800k_audit_prioritization.py` | Section 6 Table 4 | ✅ 实现 + 测试通过 |

### 3.2 缺失的计划模块（与论文当前版本无关）

| 计划模块 | AGENTS.md 目标路径 | 当前状态 | 对论文影响 |
|----------|-------------------|----------|------------|
| 条件干预分布 | `src/fma/conditional/` | **无文件** | 论文未使用；当前 replacement 用随机模板 swap |
| 反事实匹配 | `src/fma/matching/` | **无文件** | 论文未使用；AGENTS.md 4.2 为算法模板 |
| 双重稳健估计 | `src/fma/dr/` | **无文件** | 论文未使用；AGENTS.md 4.3 为算法模板 |

**关键判断**：这三个缺失模块属于 `Planned Modules (NOT YET IMPLEMENTED)`，是论文未来扩展方向（counterfactual matching、DR correction），而非当前 SC-FMA 方法的核心依赖。论文方法基于凸优化校准（SCU objective），不涉及 matching 或 DR。因此，**这些缺失模块不构成当前投稿的硬性阻碍**，但建议在 Response to Reviewers 中准备说明。

---

## 4. 投稿包格式完整性 ✅

### 4.1 已齐备的文件

| 文件 | 状态 | 备注 |
|------|------|------|
| `manuscript.pdf` | ✅ | 16 页，内容忠实 |
| `manuscript_anonymous.pdf` | ✅ | 匿名审稿版已生成 |
| `cover_letter.docx` | ✅ | scope 论证指向知识密集型信息处理 |
| `Highlights.docx` | ✅ | 5 条 bullet，符合 Elsevier 85 字符限制 |
| `supplementary.docx` | ✅ | 包含 KKT 条件、证明、扩展表、PRM800K 细节 |
| `graphical_abstract.png` | ✅ | 存在 |
| `latex_source.zip` | ✅ | 包含源码、Bib、CAS style 文件、PNG  artwork |
| `final_submission_manifest.md` | ✅ | 包清单完整 |

### 4.2 格式 checklist 状态

`format_checklist.md` 共 24 项，23 项已打勾，剩余 1 项：

- [ ] **DOCX visual rendering**：本地未安装 LibreOffice/`soffice.exe`，无法渲染验证。但 DOCX 结构和文本已通过直接检查。

**建议**：如条件允许，在可运行 LibreOffice 的环境中打开 `cover_letter.docx`、`Highlights.docx`、`supplementary.docx` 确认无乱码/格式崩坏。

---

## 5. IPM 期刊匹配度 ⚠️（最大风险项）

### 5.1 风险描述

`Information Processing & Management`（IPM）是 Elsevier 旗下信息科学/图书情报学领域期刊，传统 Aims & Scope 聚焦于：
- 信息检索（IR）理论与系统
- 信息组织、知识管理
- 信息行为、用户研究
- 数字图书馆、Web 搜索
- 信息处理方法论

**论文定位**：SC-FMA 是一个**方法论/凸优化校准**贡献，面向"知识密集型推理中的审计优先化"，属于 AI/ML 中的过程监督（process supervision）和可解释性（XAI）交叉领域。

**潜在张力**：
- 论文的技术深度（SCU 凸优化、图诊断、PRM800K 步骤排名）更偏向 *Neural Networks*、*Knowledge-Based Systems*、*Applied Soft Computing* 或 *Information Sciences* 的审稿人期待。
- IPM 的读者群更习惯看到信息检索、查询理解、文档排序、知识组织等主题。纯方法论/优化论文可能面临 scope 质疑。

### 5.2 封面信中的 scope 论证评估

封面信已尝试 framing：
> "verification steps are weighted not only by local utility, but also by graph dependencies, redundancy, and bottleneck roles, supporting audit prioritization under a fixed review budget"

这个 framing 是合理的，但强度**中等**。它成功地将方法定位为"信息密集型处理中的决策支持"（knowledge-structured decision-support），但审稿人仍可能质疑：
- 为什么不在专门的 ML/AI 期刊发表？
- 对信息检索或知识管理的直接应用在哪里？

**建议增强方向**（如不增加新实验）：
- 在封面信中增加一句话，将 SC-FMA 与信息检索中的**检索链路审计**（retrieval pipeline audit）或知识管理中的**知识图谱质量评估**（KG quality assessment）直接关联。
- 强调 Figure 1 的冗余密度分析可类比于检索结果中的冗余文档检测。
- 补充说明：虽然当前验证在 PRM800K（数学推理标注），但方法框架可直接迁移到检索-增强生成（RAG）或专家系统规则链的审计队列。

---

## 6. 具体行动清单

### 6.1 投稿前必须完成（Hard blockers）

无严格 blocker。但建议完成以下低风险项：

| # | 任务 | 优先级 | 预计时间 |
|---|------|--------|----------|
| 1 | 在含 LibreOffice 环境中打开 3 个 DOCX 确认渲染正常 | 建议 | 10 min |
| 2 | 在 cover_letter.docx 中补充 1–2 句与 IR/KG 审计的直接关联，强化 IPM scope 论证 | 建议 | 15 min |
| 3 | 检查 `manuscript.pdf` 中是否包含所有 4 个表格（Table 1–4）和 3 个图（Figure 1–3）的引用 | 建议 | 5 min |

### 6.2 投稿后可准备（Reviewer 可能提问）

| # | 任务 | 说明 |
|---|------|------|
| 4 | 准备 Response 模板，解释 `conditional/`、`matching/`、`dr/` 为 planned future work | 审稿人可能质疑"为什么不用 matching/DR" |
| 5 | 准备补充材料中 Countries-KG fixture pilot 的扩展说明 | 论文提到 ontology-edge pilot 在 supplementary，审稿人可能要求展示 |
| 6 | 准备解释为什么 Ridge 在 PRM800K 优于 QP | 论文已有详细说明，但可能需进一步简化 |

### 6.3 不必须但可改进（Nice to have）

| # | 任务 | 说明 |
|---|------|------|
| 7 | 实现 `conditional/` 目录的骨架代码（即使仅为 placeholder） | 缩小 AGENTS.md 中 planned vs implemented 差距 |
| 8 | 在 README.md 中增加 IPM 投稿状态标识 | 帮助后续维护者理解当前投稿目标 |

---

## 7. 结论

> **当前项目距离 IPM 投稿的差距很小，以 1 个中等风险（scope 匹配）和 2 个低风险项（代码未实现模块、DOCX 渲染验证）为主，不存在硬性 blocker。**

论文本身的科学严谨性（预注册、claim registry、负面结果透明、边界声明）已经达到高水平。主要不确定性来自外部：IPM 编辑和审稿人对纯方法论/AI 校准论文的接受度。

**建议决策树**：

| 条件 | 行动 |
|------|------|
| 愿意承担 scope 质疑风险 | 直接投稿 IPM，同时准备备选期刊清单（KBS、Information Sciences、Applied Soft Computing） |
| 希望降低 scope 风险 | 先投 IPM，若 desk reject 则根据反馈快速转投 KBS（论文原初即为 KBS 设计，package 已兼容） |
| 想进一步加固 | 用 30 min 增强 cover letter 的 IR/KG 关联 framing，然后投稿 |

---

*报告生成时间：基于 2026-06-22 的项目状态审阅。*
