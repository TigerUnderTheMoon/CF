# Draft: KBS 论文修复计划

## 诊断结论（已确认）

### 写作/结构问题（可通过改稿解决）
- 篇幅仅 5 页，严重不足（KBS 通常 12-20 页）
- 缺失独立 Discussion 章节
- Related Work 过简（合并为 "Related Work and Boundary"）
- 防御性写作基调（摘要 40% 篇幅在声明不主张什么）
- 大量内容被压缩至 supplementary
- PRM800K 叙事矛盾未正面解释（QP 在真实数据上退化）
- 引用文献 KBS 覆盖不足（仅 3 篇 KBS 期刊文章）

### 研究证据缺口（需要实际实验工作）
- 全部 6 条真实任务验证路径失败（GSM8K/HotpotQA）
- 无 KBS 系统集成案例
- PRM800K 上 SC-FMA QP 不如 w_struct 直接排序
- 合成基准仅 200 轨迹，外部有效性不足

## 待确认范围决策

用户需要选择修复路径：
- A: 换投更适配期刊（Neurocomputing 等），仅改稿
- B: 坚持 KBS，仅改稿（接受当前证据边界）
- C: 坚持 KBS，改稿 + 补真实任务验证 + 补 KBS 集成案例

## Open Questions
- 用户希望走哪条路径？
- 若选 C，是否有时间和资源跑新的真实任务实验？
- 若选 C，KBS 集成案例应聚焦哪个方向（RAG 审查 / KGQA / 规则引擎）？

## Scope Boundaries
- 待用户确认后填写
