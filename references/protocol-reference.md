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
| LoRaWAN | 无线专网 | 极低（电池数年） | 0.3~50 kbps | 广覆盖低速率，水表/气表/农田传感器 |
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

## 三、物模型示例（属性/事件/服务三元组）

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
  ]
}
```

## 四、Topic 命名惯例
- 属性上报：`sys/{productKey}/{deviceName}/thing/event/property/post`
- 服务调用：`sys/{productKey}/{deviceName}/thing/service/{identifier}`
- 自定义主题：`/{productKey}/{deviceName}/user/{自定义}`
- 禁止：以 `/` 开头、含空格、含中文

## 五、QoS 速判
- 遥测上报：QoS 0 或 1（QoS 2 开销大，仅用于计费类不可重复消息）
- 指令下发：QoS 1 + 业务层去重
- 告警事件：QoS 1 保证不丢
