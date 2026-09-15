# MOSFET_Data 全量器件接入主计划

状态：`ACTIVE`

## 目标

将外部 `MOSFET_Data` 语料库中的全部 PDF 依次完成清单化、数据提取与质量审核；全量提取门关闭后再注册合格器件；最后只对证据充分并通过独立验证的器件/模型计算开关损耗和生成报告。

执行规则以根目录 `AGENTS.md` 和 `docs/FLEET_ONBOARDING.md` 为准。本文件是唯一 Active plan；不得为厂商或批次另建第二份 Active Markdown plan。

## 初始规模快照（2026-09-15）

- PDF 总数：1065
- Wolfspeed：629
- Rohm：219
- Infineon：177
- Navitas：24
- Mitsubishi：16
- 重名文件组：178（必须用 SHA-256 判断是否为真正重复）

以上只用于规划，Phase 1 必须重新生成可复现清单。

## 不可违反的边界

- 外部 `MOSFET_Data` 只读，不移动、不重命名、不覆盖、不删除。
- 严格遵循“全部提取与 QA -> 注册 -> 模型与校准 -> 损耗计算”的全局顺序。
- 原始 PDF/XML、临时结果、绝对用户路径不得进入 Git。
- 任何参数都必须保留来源哈希、页码/定位、单位、条件、提取器版本和置信度。
- 缺数据时记录 blocker，不猜测参数，不把注册状态等同于可计算状态。
- 校准配置固定且版本化；预测期间不得重新拟合。

## Phase 0 — 扩展前的平台闭环

- [ ] 0.1 定义版本化 source-inventory 和 progress-ledger schema。
- [ ] 0.2 实现确定性 PDF 清单、SHA-256 和精确重复分组命令。
- [ ] 0.3 实现文档类型、技术类型和候选器件号分类字段，未知项必须显式保留。
- [ ] 0.4 建立按厂商/技术/版式版本路由的规则包机制和 golden fixture 测试。
- [ ] 0.5 将硬编码 C2M0025120D 的计算注册改为 manifest-driven discovery。
- [ ] 0.6 定义 SiC MOSFET、Si MOSFET、GaN、功率模块、二极管的适用模型边界，禁止直接复制 C2M 实现。
- [ ] 0.7 增加全流程断点续跑、终态计数对账和失败清单测试。

退出条件：测试通过；清单、规则路由、生命周期和注册发现机制能在不修改源数据的条件下扩展到多厂商。

## Phase 1 — 全量清单与去重

- [ ] 1.1 从配置的数据根目录重新发现全部 PDF。
- [ ] 1.2 为每份文件记录相对路径、大小、SHA-256、厂商、文档类型、技术类型、候选器件号和处理状态。
- [ ] 1.3 建立 byte-identical duplicate 组并指定 canonical source；保留所有来源引用。
- [ ] 1.4 对账 discovered、hashed、unique、duplicate、failed 数量。

退出条件：每一份发现的 PDF 恰好对应一个清单行和一个明确状态，数量完全对账。

## Phase 2 — 所有 PDF 数据提取与 QA

厂商执行顺序：

- [ ] 2.1 Infineon：版式分组、golden 样本、pilot、全量提取、QA、总结。
- [ ] 2.2 Mitsubishi：版式分组、golden 样本、pilot、全量提取、QA、总结。
- [ ] 2.3 Navitas：版式分组、golden 样本、pilot、全量提取、QA、总结。
- [ ] 2.4 Rohm：版式分组、golden 样本、pilot、全量提取、QA、总结。
- [ ] 2.5 Wolfspeed：版式分组、golden 样本、pilot、全量提取、QA、总结。
- [ ] 2.6 生成全语料 complete/no-match/excluded/failed/duplicate 汇总并逐项对账。
- [ ] 2.7 将未解决的单位、条件、min/typ/max、器件号和曲线归属问题转为显式 blocker。

退出条件：每个 unique PDF 有不可变提取报告和终态；所有关键 QA 问题已解决或阻塞；在此之前不得进入 Phase 3。

## Phase 3 — 器件归并与注册

- [ ] 3.1 依据已核验器件号和文档修订归并来源，不按文件名盲目建器件。
- [ ] 3.2 为合格器件生成短路径目录和 canonical DeviceRecord。
- [ ] 3.3 填充 manifest、来源哈希、曲线、支持域、缺失证据和生命周期状态。
- [ ] 3.4 通过 schema、manifest、唯一 ID、动态 registry 和来源追踪测试。
- [ ] 3.5 对二极管、模块、应用资料和证据不足器件设置正确的 NOT_APPLICABLE/BLOCKED 状态。

退出条件：注册数量、阻塞数量、非适用数量与 Phase 2 归并结果完全对账；所有已注册器件可由统一 registry 发现。

## Phase 4 — 模型就绪评估与通用化

- [ ] 4.1 按 M0/M1/M2/M3 证据矩阵评估每个已注册器件，不做默认全模型承诺。
- [ ] 4.2 优先实现可复用技术/封装模型适配器，再接入器件数据。
- [ ] 4.3 为每个 ready/blocker 判定保存机器可读原因和证据链接。
- [ ] 4.4 对所有模型增加输入域、单位、寄生参数和外推策略测试。

退出条件：每个已注册器件对每个模型都有 MODEL_READY、BLOCKED 或 NOT_APPLICABLE 判定。

## Phase 5 — 固定校准、独立 holdout 与验证

- [ ] 5.1 为每个 MODEL_READY 对创建不可变版本化 CalibrationProfile。
- [ ] 5.2 在拟合前冻结 calibration/holdout 划分并检查无交集。
- [ ] 5.3 执行参考点、趋势、跨工况、寄生变化、收敛、误差和不确定度测试。
- [ ] 5.4 明确区分 datasheet/XML 验证与独立 DPT 实测验证，并记录证据限制。
- [ ] 5.5 仅将通过门槛的器件/模型标记为 VALIDATED/BATCH_READY。

退出条件：所有声称可批量计算的器件/模型都有固定校准、独立验证结果、支持域和回归测试。

## Phase 6 — 全量开关损耗计算、处理与可视化

- [ ] 6.1 仅对 BATCH_READY 器件/模型生成确定性工况矩阵。
- [ ] 6.2 批量运行并保留 run ID、模型/校准版本、输入、寄生参数、求解状态、耗时和失败。
- [ ] 6.3 生成厂商/技术/器件/工况维度的结果汇总、误差、不确定度和关键波形图。
- [ ] 6.4 对账 completed/failed/skipped/out-of-domain，不从报告中隐藏失败项。
- [ ] 6.5 完成数据发布权限检查，再决定哪些提取数据和结果进入公共仓库。

退出条件：可复现批量结果和报告生成完成；失败及限制完整披露；完整测试与 CI 通过。

## 当前下一步

执行 Phase 0.1：设计 source inventory、duplicate group、document classification 和 progress ledger 的版本化 schema，并先提交 schema/fixture/tests 供审核；不要开始全量 PDF 提取。
