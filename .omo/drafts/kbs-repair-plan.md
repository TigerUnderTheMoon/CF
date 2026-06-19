# Draft: KBS 投稿修复计划

## 诊断发现 (已确认)

### 论文结构问题
- 篇幅仅 5 页（KBS 常规 12-20 页）
- 大量内容（算法、消融、参数分析、层别分析）被挪入 supplementary
- 缺独立 Discussion / Implementation Details 章节
- 相关工作合并为"Related Work and Boundary"，过简
- 摘要 40% 篇幅在声明"不主张什么"——防御性写作

### 科学内容问题
- 主结果（CIU 0.483 → SC-FMA QP 0.608）仅在 200 轨迹合成基准上成立
- PRM800K 叙事矛盾：w_struct(0.611) 才是主信号，SC-FMA QP(0.442) 反而退化，Ridge(0.604) 只是近似 w_struct
- 理论与实证脱节：单调性定理在 31.2% 的 R_ij>0.7 步骤对上被违反
- 形式化过度（凸优化 + 4 定理）匹配不上实证强度

### 实验证据问题
- 6 条真实任务验证路径全部失败（v2/v2.1/v2.2/v3/v3.1/legacy pilot）
- Baseline 缺关键对照：直接用 w_struct 排序（已优于所有 SC-FMA 变体）
- 缺跨数据集验证

### KBS 适配问题
- 论文核心是 PRM/process supervision，非知识系统
- 无任何真实 KBS 集成（仅方法论类比）
- KG 边缘构建 pilot 标记 validated_kbs_workflow=false
- KBS 期刊引用仅 3 篇，且非深度参与
- "knowledge-intensive" 标题与实际内容（数学推理步骤加权）不符

## 关键决策点 (待用户确认)

### 决策 1: 投稿目标
- 选项 A: 坚持 KBS，需补 KBS 集成 + 真实任务
- 选项 B: 换投更适合的期刊（Neurocomputing / Neural Networks）
- 选项 C: 先积累证据再决定

### 决策 2: 修复范围
- 范围 1: 仅论文重写（不跑新实验）
- 范围 2: 论文重写 + 重跑/补跑实验
- 范围 3: 全栈修复（含 KBS 集成新案例）

### 决策 3: 真实任务验证策略
- 路径 A: 修复 v3/v3.1 smoke test 直到通过
- 路径 B: 设计新的真实任务验证路径（避开已知失败模式）
- 路径 C: 放弃真实任务，强化合成 + PRM800K 边界声明

### 决策 4: KBS 集成方式（若选 KBS 投稿）
- 方式 1: RAG pipeline 中的检索文档审查优先级
- 方式 2: KGQA 中的路径探索步骤加权
- 方式 3: 规则引擎中的推理步骤审查标记
- 方式 4: 不做 KBS 集成，换期刊

## 研究发现 (来自已有审计文件)
- submission_lock_audit.md: submission_status = methodological_submission_possible_with_claim_boundaries
- claim_registry.md: PRM800K stratified gate = moderate
- 所有 v2-v3.1 路径 root cause = 数据稀缺 / sparse signal / deduplication 耗尽
- v3.6/v3.8 PRM800K 路径通过（in-distribution only）

## 范围边界
- INCLUDE: 论文修复（结构、叙事、实证强度、KBS 定位）
- 待定: 是否跑新实验 / 是否做 KBS 集成 / 是否换期刊

## 测试策略决策
- 待用户确认范围后决定
- 论文项目无传统 unit test，但有 verify_kbs_submission_package.py 等包验证器
- QA: 重新编译 PDF、跑格式验证器、检查 claim boundary 一致性

## 开放问题
- 用户是否接受换投非 KBS 期刊？
- 是否有计算资源跑新实验？
- 时间预算（投稿 deadline）？
