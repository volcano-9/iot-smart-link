# IoT 智联专家（IoT SmartLink Experts）

**中文**：物联网全链路专家团队，覆盖设备接入、设备数据质量检查与端到端 IoT 上云方案咨询。

**English**: A WorkBuddy expert team for IoT — device onboarding (protocol selection, thing model, gateway topology), device data quality inspection (completeness / timeliness / accuracy / consistency) and end-to-end IoT cloud solution consulting.

![banner](docs/banner.png)

![architecture](docs/architecture.svg)

## 类型 / Type

**中文**：Team 型（多角色协作团队）。三名成员：端木联（主理人/解决方案架构师）、葛连通（设备接入工程师）、甄明晰（数据质量分析师）。

**English**: Team type (multi-role collaboration). Three members: Duanmu (lead / solutions architect), Ge (device connectivity engineer), Zhen (data quality analyst).

## 团队构成 / Team

| 成员 Member | 名字 Name | 职责 Responsibility |
|------|------|------|
| 主理人 Lead | 端木联 Duanmu（物联网解决方案架构师） | 需求澄清、任务编排、平台选型、架构与成本综合、最终方案汇编 / Clarification, orchestration, platform selection, architecture & cost synthesis, final report |
| 团员 Member | 葛连通 Ge（设备接入工程师） | 协议选型（含 DL/T 645、BACnet 等行业协议）、物模型与测点设计、安全接入与 OTA、接入拓扑 / Protocol selection (incl. DL/T 645, BACnet), thing model & measurement points, security & OTA, topology |
| 团员 Member | 甄明晰 Zhen（数据质量分析师） | 完整性/时效性/准确性/一致性四维体检、异常检测、横向对比与交叉校验、流式质检、数据治理 / Four-dimension audit, anomaly detection, peer comparison & cross-validation, streaming QC, governance |

## 功能 / Features

1. **设备接入实施 / Device onboarding**：设备画像 → 协议选型 → 接入拓扑（直连/网关/边缘）→ 物模型与测点（属性/事件/服务 + tag、地址、类型、字节序、系数、量程、质量码）→ 安全 → 实施清单 / Device profile → protocol → topology (direct/gateway/edge) → thing model & points → security → step-by-step plan
2. **数据质量体检 / Data quality audit**：四维量化（完整性/时效性/准确性/一致性）→ 归因 → P0/P1/P2 分级 → 治理建议 / Four quantitative dimensions → root cause → severity grading → remediation
3. **端到端上云方案 / End-to-end cloud solution**：平台选型、架构设计、成本估算，接入与数据两路并行分析后综合 / Platform selection, architecture, cost estimation; parallel access & data analysis synthesized
4. **安全、OTA 与告警 / Security, OTA & alerting**：一机一密/X.509、TLS、密钥轮换；OTA 灰度与回滚；告警分级与去抖抑制；秒级流式质检 / Per-device credentials, TLS, key rotation; OTP canary & rollback; alert grading & debouncing; second-level streaming QC
5. **文件直接出活 / File-to-output**（skill `iot-file-intake`）：上传点表 xlsx/csv 自动转标准测点表；上传时序 CSV 自动算完整率/及时率/异常率/卡值 / Upload a point table to get a standard measurement-point table; upload time-series CSV to get completeness/timeliness/anomaly/stuck-value metrics

## 使用示例 / Example prompts

- 我想把一批传感器设备接入物联网平台，帮我选择接入协议并设计物模型。/ Help me onboard a fleet of sensors — pick the protocol and design the thing model.
- 帮我检查设备上报数据的质量，找出缺失、迟到和异常数据。/ Audit our device telemetry for missing, late and abnormal readings.
- 帮我设计一个智慧工厂的物联网上云方案，包括平台选型、架构与成本估算。/ Design an end-to-end IoT cloud solution for a smart factory, including platform choice, architecture and cost estimate.

## 输出示例（节选）/ Sample output (excerpt)

```markdown
## 二、质量总评 / Quality summary
**评级：中 / Rating: Medium**。30 台温湿度传感器 11-01–11-07 应上报 302,400 条，实收 286,455 条，
整体完整率 94.7%（未达 95% 良线），主要受 3 台设备周期性断档拖累；
异常率 0.8%（阈值 <1% 为良），集中在 2 台湿度传感器疑似卡值。

## 三、四维体检结果 / Four-dimension results
| 维度 Dimension | 指标 Metric | 数值 Value | 结论 Finding |
|------|------|------|------|
| 完整性 Completeness | 完整率 | 94.7% | 3 台设备每日 02:00–03:00 断档，疑定时重启 |
| 时效性 Timeliness | 及时率（延迟≤5s） | 99.2% | 优 |
| 准确性 Accuracy | 异常率 | 0.8% | 2 台湿度连续 60+ 周期恒为 65.0%，疑似卡值 |
| 一致性 Consistency | 重复上报 | 1,204 条 | 集中于网络抖动时段，建议 QoS 0→1 |
```

## 适用边界 / Scope limits

- **不做硬件选型与报价**：可给参数要求与成本量级，不替代采购询价 / No hardware sourcing or firm quotes; parameters and cost magnitudes only
- **不做私有协议逆向与固件开发**：私有协议需厂商接口文档 / No private-protocol reverse engineering; vendor docs required
- **不替代现场施工与合规评估**：电气安全、等保测评、消防联动需专业机构 / No on-site construction or compliance certification; use licensed professionals
- **不提供厂商未公开的内部接口细节**：按公开文档口径给参数 / Only publicly documented vendor parameters
- **不做生产安全闭环控制决策**：涉及人身/设备安全的动作必须人工确认 / No safety-critical closed-loop control decisions; human confirmation required

## 可信度约束 / Trustworthiness

**中文**：对制度条款、金额、编号、联系人四类无依据信息明确拒答，采用 `【已知】/【推断】/【待核实】` 三级标注；速判规则锁定为固定基线，保证同问同答；出错给更正与影响范围，触及电气安全/合规/采购时给具体转人工路径。详见 `references/trustworthiness-guide.md`。

**English**: Refuses to fabricate regulations, prices, IDs or contacts without evidence; uses `【Known】/【Inferred】/【To verify】` confidence labels; locks decision rules for consistent answers; corrects errors with impact analysis and routes to named human experts for safety/compliance/procurement. See `references/trustworthiness-guide.md`.

## 质量自测（双轨）/ Quality evaluation (two-track)

**中文**：包内自带可执行评测集（28 用例 + 双轨判分）。**自动轨**做字符串匹配初筛（章节/关键词/表格/禁用词/长度/反问/语种/格式红线）；**语义轨**由人工或 LLM 判断"说得对不对"，防止堆砌关键词骗分。两轨都过才可提交审核。

**English**: An executable eval suite (28 cases, two tracks). The **automated track** is a string-matching screen (sections/keywords/tables/forbidden text/length/questions/language/format red lines); the **semantic track** has a human or LLM judge whether the answer is actually correct, defeating keyword stuffing. Both tracks must pass before submission.

```bash
python eval/run_eval.py --init         # 生成 28 张用例卡 / generate 28 case cards
# 逐条发送提问，回答存到 eval/answers/<用例ID>.md / save answers
python eval/run_eval.py                # 自动初筛 → eval/report.md
python eval/run_eval.py --judge-pack   # 语义判分卡 → eval/judge_pack.md
```

自动初筛已做正负对照验证：合格样例 100 分，缺项含红线样例 37 分；反堆砌启发式可识别"堆关键词无解释"的答案。详见 `eval/README.md`。/ The automated track is validated with positive/negative controls (100 vs 37); a keyword-stuffing heuristic flags suspicious answers. See `eval/README.md`.

## 头像 / Avatars

头像位于 `avatars/`（512×512 PNG，单张 <100KB）。替换要求：PNG/JPG、512×512、正方形、清晰可辨。/ Avatars in `avatars/` (512×512 PNG, <100KB each). Replacement: PNG/JPG, 512×512, square, clearly recognizable.

## 安装 / Installation

**中文**：将专家包放到专家目录，再运行注册命令：

```
C:\Users\zhiyuan.guo\.workbuddy\plugins\marketplaces\my-experts\plugins\iot-smart-link\
```

**English**: Place the package in the experts directory and register it:

```bash
python3 scripts/register_expert.py <expert-dir>
```

## 打包分享 / Packaging

```bash
python3 scripts/package_expert.py <expert-dir>
```
