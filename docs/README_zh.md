# PowerSemiForge 中文说明

PowerSemiForge（PSForge）是一套面向功率半导体器件的大规模数据与模型流水线，目标是将以下步骤统一为可追踪、可批处理和可复现的工程过程：

1. 批量读取 PDF、XML 和已有 CSV。
2. 提取标量参数、表格、曲线资产及其工况信息。
3. 生成统一器件记录和厂商/系列/料号目录。
4. 为新器件建立模型适配器和版本化标定配置。
5. 批量展开电压、电流、温度、栅极电阻和寄生参数工况。
6. 运行模型、记录失败、汇总误差并生成图表。

当前 `C2M0025120D` 是首个完整样例，包含 M0-M3。M1-M3 的标定配置在预测前显式加载，寄生参数改变时不会重新拟合。

## 推荐规模化流程

```text
原始文件（不提交 Git）
  -> extraction-index.json 增量判定
  -> 每个源文件一个提取报告
  -> 人工/规则质量检查
  -> 版本化器件清单和曲线
  -> 模型与独立标定集
  -> holdout 验证
  -> 批量仿真和可视化
```

PDF 自动提取首先覆盖文本参数和表格。曲线数字化采用插件接口：不同厂商图形编码差异较大，不应把未经检查的像素或矢量路径直接当作最终曲线。

## 常用命令

```powershell
.\.venv\Scripts\python.exe -m powersemiforge device list
.\.venv\Scripts\python.exe -m powersemiforge extract xml --input workspace\xml --output artifacts\xml
.\.venv\Scripts\python.exe -m powersemiforge simulate --matrix examples\batch_matrix.yaml --output artifacts\runs\demo
.\.venv\Scripts\python.exe -m powersemiforge report --input artifacts\runs\demo\results.csv --output artifacts\reports\demo
```

