# PowerSemiForge 路线与状态

状态：`POWERSEMIFORGE_PUBLIC_ALPHA_READY`

路线边界：保留纯计算 API、CLI、验证和导出链路；不再开展 LTspice 仿真对比。

## Phase 0 — 工程与基线（完成）

- 工程隔离环境：`.venv`，Python 3.10.11。
- 输入包 SHA-256：`488EB69FD0A4A9B428B1D105BD4700844F49F9A222D271D329CC589A10D6DBCA`。
- 原型代码和 PDF 矢量提取 CSV 经原始测试通过。
- 原型基准记录在 `docs/phase0_baseline.json`。

## Phase 1 — 器件抽象与固定标定（完成）

- `DeviceDefinition`、`DeviceRegistry`、器件 manifest 和 Wolfspeed 适配器闭环。
- `CalibrationProfile` 与版本化 YAML 已建立。
- M1–M3 删除运行时 `_ensure_calibration()`，改为显式加载固定配置。

## Phase 2 — 统一 API 与输出契约（完成）

- `CalculationRequest`/`CalculationResult` 统一输入输出。
- 支持 M0–M3 模型选择、求解状态、来源追踪、警告和不确定度字段。

## Phase 3 — M3 主求解器（完成）

- `Lg/Ls/Lloop/Rloop` 进入动态方程或能量守恒项。
- 阶段时间连续，所有阶段有明确终止状态和最大步数。
- 返回有限值、连续时间、阶段完成状态。
- 默认使用 `dt/2` 复算，Eon/Eoff 相对变化阈值为 8%。

## Phase 4 — CLI、导出和绘图（完成）

- `estimate`、`list-devices`、`validate` 命令。
- JSON、摘要 CSV、开通/关断波形 CSV、四联关键波形 PNG。

## Phase 5 — 标定、holdout 与不确定度（完成）

- XML 端点/低电流锚点作为 calibration，`36.71 A @ 25/125°C` 作为 holdout。
- M3 XML holdout：Eon MAPE 约 6.08%，Eoff MAPE 约 9.55%。
- 寄生参数 Monte Carlo 固定随机种子，输出 5%–95% 区间。
- 证据状态：`COMPLETE_WITH_EVIDENCE_LIMITATION`，因为没有独立 DPT 实测波形。

## Phase 6 — PowerSemiForge 公共平台（完成）

- 公共包名 `powersemiforge`，CLI 为 `psforge`。
- 批量 PDF 规则提取、表格抓取、PLECS XML 提取和 SHA-256 增量索引。
- 通用器件记录 JSON Schema、设备目录脚手架和来源追踪。
- 仿真矩阵展开、失败隔离、确定性 run ID、CSV 汇总和批量图表。
- GitHub CI、MIT License、贡献指南、安全策略和数据发布边界。
- `switching_loss_engine` 保留为 C2M0025120D 的兼容计算内核。

## 下一步

新增器件时使用 `psforge device scaffold` 创建短路径目录，再增加器件适配器和固定标定/验证配置；不得在模型预测路径中重新引入现场拟合。
