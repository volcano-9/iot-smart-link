---
name: iot-file-intake
description: "Parse user-uploaded IoT files: IO/point tables (xlsx/csv) into thing-model measurement points, and time-series data (csv) into four-dimension quality metrics. Use when the user uploads a point table, device list, register map or device telemetry data for analysis."
---

# IoT 文件接入（点表 → 测点 / 数据 → 质检）

## 用途

用户上传文件时，把"人看的表格"转成"平台能用的结构"，避免靠模型目测猜列含义。

| 文件类型 | 识别特征 | 处理脚本 | 产出 |
|----------|----------|----------|------|
| 点表 / IO 表 / 寄存器表 | 列含"测点""点位""地址""寄存器""数据类型""量程" | `scripts/parse_pointtable.py` | 测点表 JSON + Markdown 表 |
| 设备清单 / 档案表 | 列含"设备ID""型号""安装位置" | 人工映射（脚本可辅助） | 设备画像 |
| 时序数据 / 历史数据 | 列含"时间""数值""设备ID" | `scripts/check_timeseries.py` | 四维质检指标 JSON + 报告 |
| 协议/手册 PDF/Word | 文档类 | 用文档读取能力抽取寄存器表 | 接入参数表 |

## 工作流程

1. **识别文件**：先读表头（前 3 行）判断属于上表哪一类；不明确时向用户确认一句
2. **点表解析**：
   ```bash
   python scripts/parse_pointtable.py <文件> --out points.json --product-key <pk>
   ```
   脚本自动按列名别名匹配（测点编码/tag、地址/寄存器、数据类型、系数、量程、周期等），
   输出标准测点结构，并把**未能匹配的列**列在 warnings 中，需人工确认是否为有效测点
3. **数据质检**：
   ```bash
   python scripts/check_timeseries.py <文件> --interval 300 --late-threshold 5
   ```
   输出完整率、及时率、异常率、卡值、重复、乱序等指标（口径见 `references/data-quality-reference.md`）
4. **交付**：把脚本产出的 JSON 与 Markdown 表贴进报告对应章节，**不得改动脚本算出的数值**；口径或参数需调整时说明改了什么

## 约束

- 脚本零第三方依赖（xlsx 用标准库解压+XML 解析），任何环境可直接运行；xlsx 结构异常时提示用户"另存为 CSV 后重试"
- 文件只读，不修改用户原文件；产出写到 `--out` 指定路径或当前目录
- 缺列、空值、单位混用时，必须在结论里显式说明影响，不得静默忽略
- 计算口径必须写进报告（预期上报周期、延迟阈值、异常判定方法），便于复核
- 禁止把用户文件的完整内容或客户敏感数据写入专家包

## 模板

- `templates/pointtable_template.csv` — 推荐的点表列结构，用户表格字段缺失时可发给用户补齐
