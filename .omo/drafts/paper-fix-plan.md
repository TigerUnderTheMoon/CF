# Draft: SC-FMA 论文修复计划

## 诊断发现（已确认）

### A. 写作/结构问题（可通过修改论文解决）
- A1: 篇幅严重不足（5页 → 需 12-20 页）
- A2: 缺失关键章节（独立实验设置、讨论、完整相关工作）
- A3: 防御性写作基调（摘要 40% 在声明不主张什么）
- A4: PRM800K 叙事矛盾（w_struct 0.611 > SC-FMA Ridge 0.604 > QP 0.442）
- A5: 理论与实证脱节（单调性定理在 31.2% 步骤对上违反）
- A6: KBS 关联薄弱（无实际 KBS 集成）
- A7: 引用文献 KBS 覆盖不足（仅 3 篇 KBS 期刊文章）
- A8: Baseline 选择性问题（缺失直接用 w_struct 或简单平均的 baseline）

### B. 研究证据缺口（需要实际跑实验）
- B1: 全部 6 条真实任务验证路径失败（GSM8K/HotpotQA）
- B2: 无 KBS 系统集成案例
- B3: 合成基准仅 200 轨迹，外部有效性未证
- B4: PRM800K 结果中 SC-FMA QP 退化（0.442 vs w_struct 0.611）

## 战略选择（待用户确认）

用户需要选择修复路径，这决定了计划范围：
- 路径 1: 换投更适合的期刊（Neurocomputing 等），只做写作重构
- 路径 2: 坚持 KBS，但只修写作/结构问题，接受当前证据边界
- 路径 3: 坚持 KBS，补真实任务验证 + KBS 集成案例（重工作量）

## 约束（来自 AGENTS.md）
- 必须遵守 claim_registry.md 的 claim boundary
- 不能 overclaim（不能将 failed_validation 升级为 supported）
- 真实任务验证失败必须保持 failed_validation / pilot_blocked 状态
- KBS 集成案例必须标记 validated_kbs_workflow=false 直到真正验证

## 开放问题
- 用户选择哪条战略路径？
- 是否需要包含真实任务验证的实验工作？
- 是否需要 KBS 集成案例研究？
