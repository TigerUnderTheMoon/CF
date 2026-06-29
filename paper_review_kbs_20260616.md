# SC-FMA 论文审阅报告（KBS 提交版 `manuscript.tex`）

> 审阅日期：2026-06-16  
> 审阅对象：`paper/kbs_submission/final_source/manuscript.tex`  
> 附带比对：`paper/ipm_submission/final_source/manuscript.tex`  
> 依据：项目 `AGENTS.md` 治理约束、`paper/claim_registry.md` 声明边界

---

## 一、审阅结论总览

| 维度 | 评级 | 说明 |
|------|------|------|
| **声明安全性（Claim Safety）** | ✅ 通过 | 未检测到将 `failed_validation`/`pilot_blocked` 升级为 `supported` 的措辞；`validated_kbs_workflow=false` 在多处显性标注；GSM8K/HotpotQA 失败路由保留透明披露。 |
| **格式合规性** | 🟡 需修正 | 存在行尾符不一致（`\r`）、附录表格手动编号、多 `\label` 堆叠等 LaTeX 技术问题。 |
| **结构清晰度** | 🟡 需优化 | Section 6.1 四重 `\label` 堆叠导致引用歧义；Section 6 与 Section 7 的边界在初读时不够清晰；IPM 版与 KBS 版结构差异较大。 |
| **写作质量** | 🟡 可打磨 | 部分句子过长（>40 词），摘要信息密度过高；术语使用存在轻微不一致；数值在摘要与正文间存在微小出入。 |
| **叙事连贯性** | ✅ 良好 | 证据路线（route-level accounting）与声明边界贯穿全文，负面/降级结果未被隐藏，与 claim registry 一致。 |

---

## 二、🔴 必须修正（Must Fix）— 格式与结构

### 2.1 多 `\label` 堆叠导致引用歧义（Line 569–572）

**问题：**
```latex
\subsection{Audit Interpretation}
\label{sec:why-calibration}
\label{sec:audit-interpretation}
\label{sec:audit-results}
\label{sec:oracle-auto-validation}
```

一个 subsection 标题后连续定义了 4 个 `\label`。在 LaTeX 中，同一对象上的多个 `\label` 不会报错，但 `\ref` 引用时只会解析到最后一个（`sec:oracle-auto-validation`），前三个会指向同一位置但依赖编译器行为，极其脆弱。文中实际有引用 `Appendix~\ref{app:failure-taxonomy}` 等，但正文中的 `\ref` 是否引用了这些歧义 label 需逐一核对。

**建议：**
- 将内容拆分为逻辑独立的子节，每个子节一个 `\label`。
- 如果必须合并，只保留一个主 `\label`（如 `\label{sec:audit-interpretation}`），其余用 `\hypertarget` 或删除。

### 2.2 附录表格脱离标准 `table` 环境（Line 674–690, 697–715, 720–739, 744–762, 771–784）

**问题：** 附录中的 5 个表格全部使用手动计数：
```latex
\refstepcounter{table}\label{tab:failure-taxonomy}
\noindent\textbf{Table~\thetable:} Reviewer V2 failure taxonomy distribution...
\begin{center}...
```

这导致：
1. 表格无法被 `\listoftables` 捕获；
2. 跨页时不会作为浮动单元保持在一起；
3. `\label` 与 `\refstepcounter` 的组合虽然可工作，但依赖 `center` 环境内的局部定义，引用不稳定；
4. 与正文中使用标准 `table` 环境的表格风格不一致。

**建议：** 统一包裹在 `\begin{table}[ht]` ... `\end{table}` 中，使用标准 `\caption` 和 `\label`。若需控制标题格式，可重定义 `\caption` 样式，而非手动编号。

### 2.3 行尾符不一致（全文 `\r`）

**问题：** 文件使用纯 `\r`（CR）行尾，而非标准 `\n`（LF）或 `\r\n`（CRLF）。这可能导致：
- 某些 LaTeX 编译器或版本控制工具（Git）将整文件视为单行；
- 与模板文件混编时产生编译警告。

**建议：** 统一转换为 `\n`（LF）或 `\r\n`（CRLF），并在项目 `.gitattributes` 中声明 `*.tex text eol=lf`。

### 2.4 摘要数值与正文不一致

**问题：**
- **Abstract**（Line 88）："200 traces (approximately 1,000 reflective steps, varying slightly by seed)"
- **正文 Table 1（Runtime）**（Line 779）："SCU Component Contribution — 200 traces, **1,008** steps"
- **正文 Table 3（Ranking）**（Line 316）："200 traces, approximately 1,000 steps"
- **IPM 版本 Abstract**（Line 55）："200 traces and **1,027** reflective steps"

步骤数在 1,000 / 1,008 / 1,027 之间不一致。如果五种子子集的步数不同，应明确说明；如果固定，应统一为精确值。

**建议：** 摘要中改为 "200 traces, ~1,000 steps (exact count varies by seed, e.g., 1,008 for seed 42)" 或直接引用范围。

---

## 三、🟡 应当修正（Should Fix）— 写作与清晰度

### 3.1 摘要过长、单句信息过载

**问题：** KBS 版摘要为一个超长段落（约 180–200 词），包含大量数字和方法论细节。Elsevier CAS 模板的摘要通常偏好简洁（<250 词是允许的，但可读性更重要）。

**当前片段：**
> "On a controlled synthetic step-importance benchmark, the QP variant shows the intended calibration behavior in a high-structure-conflict setting, increasing mean Spearman correlation with proxy step labels from 0.483 for raw CIU to 0.597. On PRM800K process supervision annotations (4,417 samples and 34,219 labeled steps under a frozen hash split), the stored \texttt{w\_struct} ranking is the primary direct ranker (Spearman 0.611), and SC-FMA Ridge closely preserves this signal (0.604) while exposing decomposable priority rules for audit. An automatic oracle audit-target validation provides rule-derived evidence that SC-FMA decomposition retrieves bottleneck, redundancy, weak-anchor, and structural-overcorrection targets more effectively than a \scalarOnly{} \texttt{w\_struct} view (mean Recall@25\% 0.699 versus 0.235; mean NDCG@25\% 0.978 versus 0.353)."

**建议：** 拆分为 2–3 句，降低每句负载：
```latex
On a controlled synthetic benchmark, SC-FMA QP improves mean Spearman 
 correlation from 0.483 (raw CIU) to 0.597. On PRM800K (4,417 samples, 
 34,219 steps), the stored \texttt{w\_struct} ranking is the primary signal 
 (Spearman 0.611); SC-FMA Ridge preserves it at 0.604 while exposing 
 decomposable audit fields. An oracle validation shows that SC-FMA 
 decomposition retrieves bottleneck, redundancy, weak-anchor, and 
 over-correction targets more effectively than a scalar-only view 
 (Recall@25\% 0.699 vs. 0.235; NDCG@25\% 0.978 vs. 0.353).
```

### 3.2 术语轻微不一致

| 术语变体 | 出现位置 | 建议 |
|----------|----------|------|
| `KBS` / `knowledge-based systems` / `knowledge-intensive systems` / `knowledge-intensive reasoning` | 全文 | 在引言中明确定义缩写 `KBS` 后，全文统一使用 `KBS` 或展开式，避免混用。 |
| `process supervision` / `process-supervision` | Abstract vs. 正文 | 统一为一种连字符用法。 |
| `fixed-budget` / `\fixedBudget{}` | 正文多处 | 检查宏定义是否在所有情况下都正确展开。 |
| `audit prioritization` / `audit-prioritization` | 标题 vs. 正文 | 统一。 |

### 3.3 Section 6 与 Section 7 的边界模糊

**问题：**
- Section 5: "KBS Implications and Limitations"（含 KBS Implications + Limitations + Scope）
- Section 6: "Discussion: Audit Interpretation and Practical Implications"（含 Audit Interpretation + Practical Implications + Oracle Validation）
- Section 7: "Conclusion"

初读时，Section 5 和 Section 6 都涉及 "implications"，容易混淆。实际上 Section 6 的核心是 **audit demonstration results**，而标题却用了 "Discussion"。

**建议：** 将 Section 6 标题改为更具体的 `"Audit Prioritization Demonstration and Interpretation"`，与 IPM 版本保持一致（IPM 版 Section 6 标题为 `"Audit Prioritization Demonstration"`，更清晰）。

### 3.4 段落过长（>15 行）

**问题位置：**
- Section 3.4 "Why Structure Adds Value"（Line 265–267）：段落极长，可拆分为 "贡献总结" + "解释性说明"。
- Section 4.4 "PRM800K Error Case Analysis"（Line 498）：长达一整页的段落，建议按子主题（trace length / label entropy / variant behavior / diagnostic finding / KBS implications）拆分为独立段落。

---

## 四、🟢 可优化（Nice to Have）— 排版与打磨

### 4.1 `\Needspace` 的孤立使用

**问题：** Line 105 使用了 `\Needspace{8\baselineskip}`，但全文仅此一处。若需控制孤行/寡行，建议在导言区统一设置 `\clubpenalty` / `\widowpenalty`，或局部使用 `\nopagebreak`，保持风格一致。

### 4.2 自定义命令的过度使用

**问题：** 导言区定义了大量 `\mbox` 包裹的命令（`\tfidf`, `\kgAssisted`, `\retrievalAugmented` 等共 12 个）。`\mbox` 会阻止连字符断词，在窄栏中可能导致 overfull hbox。如果这些术语确实不需要断词，保留；否则建议改为 `\text{...}` 或 `\textit{...}` 并允许正常断词。

### 4.3 数学符号的间距

**问题：** `Eq.~\ref{eq:scu}` 中的 `~` 使用正确，但部分地方如 `"$\rho = -0.077$"` 前后缺少 tie（`~`），在换行时数字可能孤立于行首。建议统一检查 `"$\rho = ...$"` 前的空格是否改为 `~`。

### 4.4 引用列表中的空格

**问题：** `\cite{...}` 列表有时使用 `~\cite{...}`，有时直接紧跟在前文后。建议统一为 `~\cite` 以避免行首出现引用编号。

---

## 五、声明安全审计（Claim Safety Audit）

逐条核对论文中主要声明与 `claim_registry.md` 的一致性：

| 论文声明 | Claim Registry 状态 | 结论 |
|----------|-------------------|------|
| "GSM8K/HotpotQA task-specific replay routes are retained as failed or incomplete validation attempts" | `failed_validation` / `pilot_blocked` | ✅ 一致 |
| "validated_kbs_workflow=false"（Line 445, 542） | `validated_kbs_workflow=false` | ✅ 一致 |
| "No downstream PRM training" | `F_PRM_TRAINING` = `future_validation` | ✅ 一致 |
| "No causal identification" | 明确禁止 | ✅ 一致 |
| QP synthetic Spearman 0.597 vs raw CIU 0.483 | `M_SCFMA_CALIBRATION` = `supported` | ✅ 一致 |
| PRM800K `w_struct` 0.611, Ridge 0.604 | `M_STEP_RANKING` = `supported` | ✅ 一致 |
| Oracle validation Recall@25% 0.699 vs 0.235 | `M_KBS_AUDIT_DEMONSTRATION` = `supported` | ✅ 一致 |
| MuSiQue 作为 supplementary feasibility | `M_MUSIQUE_CONSTRUCTED_FEASIBILITY` = `archived` | ✅ 一致 |
| Countries-KG pilot 为 diagnostic | `M_KG_ONTOLOGY_EDGE_PILOT` = `supported` (pilot) | ✅ 一致 |

**未发现问题：** 论文未尝试将 v2/v2.1/v2.2/v3/v3.1 的失败路由改写为正面结果；未声称 PRM 训练改进；未声称生产 KBS 验证。叙事与证据边界一致。

---

## 六、KBS 版与 IPM 版差异提醒

以下差异需在投稿前确认是否故意：

| 项目 | KBS 版 | IPM 版 | 备注 |
|------|--------|--------|------|
| 总长度 | ~18 页（含附录） | ~12 页 | KBS 允许更长 |
| 附录 | 有（Failure Taxonomy, Audit Cards, Runtime） | 无 | IPM 可能将附录移至 supplementary |
| Section 6 | "Discussion: Audit Interpretation..." | "Audit Prioritization Demonstration" | 标题差异大 |
| Oracle validation 表格 | 有（Table 9） | 无 | KBS 独有 |
| Audit Card 表格 | 有（Table 10–12） | 无 | KBS 独有 |
| Synthetic steps | "~1,000" / 1,008 | "1,027" | 数值不一致，需统一 |
| Keywords | 6 个 | 6 个（不同） | KBS 用 `knowledge-based systems`；IPM 用 `knowledge-intensive information processing` 等 |

**建议：** 如果两个版本同时维护，应建立 `diff` 清单并确保数据口径一致。当前两个版本的 `synthetic benchmark` 步数差异（1,008 vs 1,027）应被消除。

---

## 七、修正优先级清单

### 🔴 P0 — 投稿前必须修正
1. [ ] 拆分 Section 6.1 的 4 重 `\label` 堆叠（Line 569–572）。
2. [ ] 将附录 5 个手动编号表格迁移至标准 `table` 环境（Line 674–784）。
3. [ ] 统一行尾符为 `\n`（全文）。
4. [ ] 核对摘要与正文的 synthetic steps 数值（1,000 vs 1,008 vs 1,027）。

### 🟡 P1 — 强烈建议修正
5. [ ] 拆分摘要中的超长句，提升可读性。
6. [ ] 统一全文术语（KBS / knowledge-intensive / process supervision 的连字符用法）。
7. [ ] 将 Section 6 标题改为 `"Audit Prioritization Demonstration and Interpretation"` 或类似，消除与 Section 5 的语义重叠。
8. [ ] 拆分 Section 4.4 的长段落（>30 行）为逻辑子段。
9. [ ] 检查 `\mbox` 命令是否导致 overfull hbox，必要时替换为 `\text`。

### 🟢 P2 —  polish 优化
10. [ ] 统一 `\Needspace` 使用策略，或改用全局孤行/寡行控制。
11. [ ] 检查数学符号前的 tie（`~`）使用一致性。
12. [ ] 建立 KBS/IPM 双版本数据一致性校验脚本，避免 future drift。

---

## 八、治理红线声明

本次审阅 **未发现** 以下违规行为：
- 将 `failed_validation` 或 `pilot_blocked` 结果改写为正面结果。
- 添加未经支持的下游性能声明（如 PRM 训练改进、效率提升）。
- 修改数值结果或实验结论。
- 违反预注册约束或放宽 gate 门槛。
- 将 FMA 框架表述为 "true causal effect" 或 "average treatment effect"。

论文的保守证据层级（route-level accounting）和显式声明边界（NOT claimed 列表）与项目治理文件完全一致。

---

*报告生成完毕。如需针对上述任一条目生成可直接执行的 `\edit` 操作（如 `old_string`/`new_string` 的 LaTeX 修改），请提供具体条目编号，我可输出精确替换文本。*
