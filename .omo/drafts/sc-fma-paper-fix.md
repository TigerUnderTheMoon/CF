# Draft: SC-FMA 论文修复计划

## 诊断结论（已确认）

### A. 写作/结构问题（可通过修改论文解决）
- A1: 篇幅严重不足（5 页 vs KBS 常规 12-20 页）
- A2: 缺失独立 Discussion、实验设置、实现细节章节
- A3: 相关工作过简（1 节合并 Related Work + Boundary）
- A4: 防御性写作基调过重（摘要 40%+ 在声明不主张什么）
- A5: PRM800K 叙事矛盾未正面解释（为何 QP 退化？为何不直接用 w_struct？）
- A6: 理论与实证脱节（4 个定理 vs PRM800K 上 QP 退化）
- A7: 合成 proxy label 的 baseline 选择性问题（缺直接平均、缺 w_struct-only）
- A8: KBS 相关文献覆盖不足（仅 3 篇 KBS 期刊文章）

### B. 研究证据缺口（需要实际跑实验）
- B1: 全部 6 条真实任务验证路径失败（GSM8K 0/25, HotpotQA 28/35 等）
- B2: 无 KBS 系统集成案例（仅方法论类比，validated_kbs_workflow=false）
- B3: PRM800K 上 SC-FMA QP 退化（0.442 vs w_struct 0.611）
- B4: 缺少跨数据集外部有效性证据

### C. 战略选择问题
- C1: 目标期刊是否仍为 KBS？还是换投更匹配的期刊（Neurocomputing 等）？
- C2: 是否投入资源做真实任务验证 + KBS 集成案例？
- C3: 若不补研究证据，论文的 KBS 投稿门槛差距无法关闭

## 待确认的关键决策

### 决策 1：目标期刊与范围
选项：
- (A) 坚持 KBS，仅修复写作/结构问题（接受当前证据边界）
- (B) 坚持 KBS，补真实任务验证 + KBS 集成案例（重工作量）
- (C) 换投更匹配的期刊（Neurocomputing / AI Open 等），仅修复写作

### 决策 2：实验补强程度
- 是否需要新跑实验？
- 是否需要新写 KBS 集成代码？
- 还只是重新分析现有 artifacts？

### 决策 3：claim boundary 处理
- 保持现有诚实声明，还是重构为正向叙事？
- 是否允许将部分补充材料内容移回正文以增加篇幅？

## 已知约束（来自 AGENTS.md）
- 不能升级 failed_validation 路径为 passed
- 不能声称 downstream PRM training gains
- 不能声称 GSM8K/HotpotQA replay-pass
- 不能声称 formal causal identification
- 必须保持 validated_kbs_workflow=false 直到有真实 KBS 集成
- PRM800K 证据仅支持 M_STEP_RANKING 和 M_BASELINE_COMPARISON_CONTEXT_ONLY

## Open Questions
- 用户的目标期刊选择？
- 用户愿意投入多少研究工作量？
- 时间线约束？
