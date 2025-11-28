# TCP 网关与 HJ212 协议集成说明

## 架构概览

我们已经成功实现了完整的 HJ212 协议数据采集链路：

```
数采仪设备 → TCP Gateway (9880端口) → HJ212 Parser → TDengine 存储
```

## 已实现的组件

### 1. HJ212 协议解析器 (`backend/app/protocols/`)

- **parser.py**: 核心解析器，支持 HJ 212-2017 和 HJ 212-2025 双版本
- **enums.py**: 命令码、参数码定义
- **crc.py**: CRC16 校验算法
- **models.py**: Pydantic 数据模型
- **tdengine_schema.py**: TDengine 表结构定义

特性：
- ✅ 自动版本检测（通过 Flag 位运算）
- ✅ 支持水质、空气、电力等全系列参数
- ✅ CRC16 校验
- ✅ 分包处理
- ✅ SM4 解密预留接口

### 2. TCP Gateway 服务器 (`backend/app/gateway/server.py`)

- 监听端口：9880
- 异步处理多个并发连接
- 接收 HJ212 报文 → 解析 → 存储 → 发送 ACK

### 3. TDengine 集成 (`backend/app/db/`)

- **tdengine_client.py**: 异步客户端封装
- **tdengine_schema.py**: 超级表定义，包含所有监测参数

表结构：
- 超级表：`meters_data`
- Tags：设备号(mn)、站点名称、位置、协议版本等
- Metrics：w系列(水质)、a系列(空气)、d系列(电力)、p系列(生产工况)

### 4. FastAPI 集成 (`backend/app/main.py`)

TCP Gateway 已集成到 FastAPI 生命周期：
- 启动时自动启动 TCP Server
- 关闭时优雅停止

## 使用方法

### 启动服务

1. **启动 FastAPI + TCP Gateway**:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后：
- API 服务：http://localhost:8000
- TCP Gateway：localhost:9880

### 测试数据采集

使用模拟设备脚本测试：

1. **发送单条 HJ 212-2017 水质数据**:
```bash
cd backend
python scripts/mock_device.py --type 2017
```

2. **发送单条 HJ 212-2025 电力数据**:
```bash
python scripts/mock_device.py --type 2025
```

3. **发送空气质量数据**:
```bash
python scripts/mock_device.py --type air
```

4. **连续发送测试（每10秒一条）**:
```bash
python scripts/mock_device.py --type continuous --interval 10
```

5. **自定义设备ID和服务器**:
```bash
python scripts/mock_device.py \
    --device-id "123456789012345678901234" \
    --host "192.168.1.100" \
    --port 9880 \
    --type continuous
```

### 模拟设备脚本参数

```
--host          TCP服务器地址 (默认: localhost)
--port          TCP服务器端口 (默认: 9880)
--device-id     24位设备ID (默认: 888888888888888888888888)
--type          数据类型:
                - 2017: HJ 212-2017 水质数据
                - 2025: HJ 212-2025 电力数据
                - air: 空气质量数据
                - heartbeat: 心跳包
                - continuous: 连续发送模式
--interval      连续模式发送间隔(秒) (默认: 10)
```

## 数据流程

1. **设备发送数据**:
   - 数采仪通过 TCP 连接到 9880 端口
   - 发送符合 HJ212 协议的数据包

2. **Gateway 接收处理**:
   - TCP Server 接收原始字节流
   - 调用 HJ212Parser 解析数据
   - 验证 CRC、提取参数值

3. **数据存储**:
   - 解析成功的数据写入 TDengine
   - 每个参数作为一条时序数据记录
   - 自动创建设备子表

4. **应答响应**:
   - 如果 Flag 标志需要应答
   - 生成并发送 ACK 报文（CN=9014）

## 监控与调试

### 查看日志

服务运行时会输出详细日志：
- 新连接信息
- 解析的消息详情
- 存储结果
- ACK 发送状态

### 查看统计信息

TCP Server 维护运行统计：
```python
server.get_stats()
# 返回：
# {
#     'messages_received': 100,
#     'messages_parsed': 98,
#     'messages_stored': 96,
#     'messages_failed': 2,
#     'connections_total': 5,
#     'connections_active': 2
# }
```

### TDengine 数据查询

连接 TDengine 查看数据：
```sql
-- 查看最新数据
SELECT LAST(*) FROM ecomind.meters_data;

-- 查看特定设备数据
SELECT * FROM ecomind.device_888888888888888888888888
ORDER BY ts DESC
LIMIT 100;

-- 统计各设备数据量
SELECT device_id, COUNT(*)
FROM ecomind.meters_data
GROUP BY device_id;
```

## 注意事项

1. **端口占用**: 确保 9880 端口未被占用
2. **TDengine**: 需要先安装并启动 TDengine 服务
3. **设备ID**: 必须是 24 个字符
4. **CRC校验**: 默认启用，可在 ParserConfig 中配置
5. **SM4加密**: 2025版本预留了接口，需要时可集成

## 扩展开发

### 添加新参数

在 `enums.py` 中添加参数定义：
```python
# 新参数
X12345 = "x12345"  # 参数说明

# 更新映射
PARAMETER_DESCRIPTIONS["x12345"] = "参数说明"
PARAMETER_UNITS["x12345"] = "单位"
```

### 自定义处理逻辑

在 `server.py` 的 `store_data` 方法中添加：
```python
# 特殊参数处理
if param_code == "x12345":
    # 自定义逻辑
    pass
```

## 故障排查

1. **连接失败**:
   - 检查防火墙设置
   - 确认服务已启动
   - 验证端口是否正确

2. **解析失败**:
   - 检查报文格式
   - 验证 CRC 校验
   - 查看错误日志

3. **存储失败**:
   - 确认 TDengine 运行正常
   - 检查表是否创建
   - 查看数据库连接

## 性能优化

- 使用 uvloop 提升异步性能
- 批量写入 TDengine（可选）
- 连接池管理（已实现单例）
- 消息队列缓冲（可扩展）

## 总结

整个 HJ212 协议数据采集链路已经完全打通：

1. ✅ 协议解析器支持 2017/2025 双版本
2. ✅ TCP Gateway 异步高性能处理
3. ✅ TDengine 时序数据存储
4. ✅ FastAPI 集成
5. ✅ 模拟设备测试工具

系统已经可以接收真实数采仪的数据，并进行解析、存储和应答。