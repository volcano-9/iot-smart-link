# 设备接入参考知识（协议 / 物模型 / Topic / QoS）

> 供 device-access-engineer 与主理人引用。若当前环境无法读取本文件，直接依据成员 MD 内的「速判规则」作答即可。

## 一、接入协议参数对比表

| 协议 | 传输层 | 功耗 | 带宽/速率 | 典型场景 |
|------|--------|------|-----------|----------|
| MQTT | TCP | 低（长连接+心跳） | 按网络 | 设备云上报首选，支持 QoS 0/1/2，主题订阅/发布 |
| MQTT-SN | UDP | 极低 | 窄带 | 无 TCP 栈的受限设备，常与网关配合 |
| CoAP | UDP | 极低 | 窄带 | 资源受限设备（Constrained Node），REST 风格，报文小 |
| HTTP/HTTPS | TCP | 高（每次建连） | 按网络 | 低频上报、固件下载、调试友好 |
| Modbus RTU/TCP | 串口/TCP | - | 低（主从轮询） | 工业现场 PLC/仪表，经网关转 MQTT 上云 |
| OPC UA | TCP | - | 中 | 工业高层语义互操作，工厂 MES/SCADA 对接 |
| LoRaWAN | 无线专网 | 极低（电池数年） | 0.3–50 kbps | 广覆盖低速率，水表/气表/农田传感器 |
| NB-IoT | 蜂窝授权频段 | 低 | <250 kbps | 无本地网关、广覆盖，抄表/烟感/井盖 |
| Zigbee | 2.4G mesh | 极低 | 250 kbps | 短距离多设备组网，智能家居，经网关上云 |
| DL/T 645 | 串口（RS-485）/ 红外 | - | 低 | 电力行业电表通信标准（国内），抄表常用 645-2007 |
| CJ/T 188 | 串口 / M-Bus | - | 低 | 城镇供水/燃气/热量表通信协议（国内行业标准） |
| M-Bus | 两线总线 | 总线供电 | 低（主从轮询） | 欧洲/国内水表热表总线抄表，可给表计供电 |
| BACnet | TCP/UDP（BACnet/IP）或 MS/TP（RS-485） | - | 低 | 楼宇自控（暖通、照明、电梯）主流标准 |
| KNX | 专用总线 | 总线供电 | 低 | 楼宇/家居开关照明控制，欧洲体系 |
| CAN / J1939 | CAN 总线 | - | 中 | 车辆/工程机械数据采集，J1939 为商用车应用层 |
| PROFINET / EtherCAT | 工业以太网 | - | 高（实时） | 产线实时控制层，一般不直接上云，经边缘汇聚 |

## 二、选型速判
- 电池供电 + 无本地网关 → NB-IoT / LoRaWAN
- 有 WiFi / 以太网 → MQTT 直连
- 工业改造 → Modbus / OPC UA + 网关
- 每秒高频采集 → MQTT QoS 1 + 批量合并上报
- 低频上报 / 固件下载 → HTTPS
- 电力抄表（国网体系）→ DL/T 645 + 集中器/网关转 MQTT
- 水务/燃气/热力表计 → CJ/T 188 或 M-Bus + 集中器
- 楼宇自控 → BACnet/IP（新系统）或 BACnet MS/TP、KNX（存量）+ 协议网关
- 车辆/工程机械 → CAN + J1939 报文解析，经车载终端上云
- 产线实时控制 → PROFINET/EtherCAT 留在现场层，边缘汇聚后按分钟级上云

## 三、物模型与测点（属性/事件/服务 + 测点层）

物模型不能只写属性/事件/服务——**每个属性背后必须落到具体测点（measurement point / tag）**，否则设备侧采不到、平台侧解析不了，联调必然返工。

分层关系：产品 → 设备 → 物模型（属性/事件/服务）→ **测点**（设备侧最小采集单元，映射到物理通道/寄存器/报文位置）

### 3.1 测点定义字段（缺一项都可能在联调时返工）

| 字段 | 说明 | 示例 |
|------|------|------|
| 测点编码 tag | 设备内唯一，建议 `设备类型_物理量_序号` | TH_TEMP_01 |
| 关联属性 identifier | 对应物模型属性 | temperature |
| 数据类型 | bool/int16/int32/float32/double/enum/string | float32 |
| 采集通道 | 协议 + 地址定位 | Modbus：slave=1, FC=03, addr=0x0000；OPC UA：`ns=2;s=Ch1.Dev1.Temp` |
| 字节序/字序 | 大端 ABCD / 小端 DCBA / 字交换 CDAB、BADC | CDAB（float32 最常踩的坑） |
| 缩放系数与偏移 | 工程值 = 原始值 × 系数 + 偏移 | ×0.1, +0 |
| 单位 | 与属性单位一致 | ℃ |
| 量程 | min/max，用于超量程判定 | -40 / 85 |
| 采集周期 | 秒，可与上报周期不同 | 300 |
| 死区/变化阈值 | 变化超过阈值才上报 | 0.2 |
| 质量码 | 有效 / 超量程 / 通讯故障 / 无效 | 0 = 有效 |
| 告警阈值 | 高 / 低 / 高高 / 低低 | 高 60℃ |
| 安装位置 | 物理位置，便于现场排查 | 1#车间东侧 |

### 3.2 物模型 JSON 示例（含测点映射）

```json
{
  "productKey": "a1B2C3d4E5f",
  "properties": [
    { "identifier": "temperature", "name": "温度", "dataType": "float", "unit": "℃", "min": -40, "max": 85, "step": 0.1, "accessMode": "r" },
    { "identifier": "humidity", "name": "湿度", "dataType": "float", "unit": "%RH", "min": 0, "max": 100, "accessMode": "r" },
    { "identifier": "reportInterval", "name": "上报周期(秒)", "dataType": "int", "min": 10, "max": 3600, "accessMode": "rw" }
  ],
  "events": [
    { "identifier": "overheatAlarm", "name": "过温告警", "type": "alert", "outputData": [{ "identifier": "temperature", "dataType": "float" }] }
  ],
  "services": [
    { "identifier": "reboot", "name": "重启设备", "callType": "sync", "inputData": [], "outputData": [{ "identifier": "result", "dataType": "bool" }] }
  ],
  "measurementPoints": [
    {
      "tag": "TH_TEMP_01", "property": "temperature", "dataType": "float32",
      "channel": "modbus:slave=1,fc=03,addr=0x0000", "byteOrder": "CDAB",
      "scale": 0.1, "offset": 0, "unit": "℃", "min": -40, "max": 85,
      "sampleInterval": 300, "deadband": 0.2, "qualityCode": "valid",
      "alarm": { "high": 60, "low": -10 }, "location": "1#车间东侧"
    },
    {
      "tag": "TH_HUMI_01", "property": "humidity", "dataType": "float32",
      "channel": "modbus:slave=1,fc=03,addr=0x0002", "byteOrder": "CDAB",
      "scale": 0.1, "offset": 0, "unit": "%RH", "min": 0, "max": 100,
      "sampleInterval": 300, "deadband": 0.5, "qualityCode": "valid"
    }
  ]
}
```

### 3.3 测点设计四条铁律

1. **一一映射**：一个属性至少对应一个测点；同一物理量分布在多个位置时，用不同 tag 区分（如 `A区_TEMP_01`、`B区_TEMP_01`），不得合并成一个属性
2. **地址可追溯**：测点必须记录通道地址与解析规则（寄存器/对象路径/报文偏移），否则现场换表、换网关后无法重映射
3. **字节序先验证**：float32 读数明显离谱（如 1.2e-38、几万度）时，先怀疑字节序/字序，而不是传感器损坏
4. **质量码不可省**：必须区分"数值为 0"与"采集失败"，否则数据质量分析会把通讯故障当成真实读数

## 四、Topic 命名惯例
- 属性上报：`sys/{productKey}/{deviceName}/thing/event/property/post`
- 服务调用：`sys/{productKey}/{deviceName}/thing/service/{identifier}`
- 自定义主题：`/{productKey}/{deviceName}/user/{自定义}`
- 禁止：以 `/` 开头、含空格、含中文

## 五、QoS 速判
- 遥测上报：QoS 0 或 1（QoS 2 开销大，仅用于计费类不可重复消息）
- 指令下发：QoS 1 + 业务层去重
- 告警事件：QoS 1 保证不丢
