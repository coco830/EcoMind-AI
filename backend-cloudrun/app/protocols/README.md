# HJ212 Protocol Parser

纯 Python 实现的 HJ212 协议解析器，支持 HJ 212-2017 和 HJ 212-2025 版本。

## 特性

- ✅ 支持 HJ 212-2017 和 HJ 212-2025 双版本
- ✅ 自动版本检测（通过 Flag 字段）
- ✅ CRC16 校验
- ✅ 分包处理支持
- ✅ Pydantic 模型验证
- ✅ 支持所有标准参数编码（水质、空气、电力、生产工况等）
- ✅ 预留 SM4 加密解密接口（2025版本）

## 项目结构

```
backend/app/protocols/
├── __init__.py       # 模块导出
├── enums.py         # 枚举定义（命令码、参数码等）
├── crc.py           # CRC16 校验算法实现
├── models.py        # Pydantic 数据模型
├── parser.py        # 核心解析器
└── README.md        # 本文档
```

## 快速使用

### 基本解析

```python
from app.protocols.parser import HJ212Parser

# 创建解析器实例
parser = HJ212Parser()

# 解析报文
raw_packet = b"##0198QN=20240101120000000;ST=31;CN=2011;..."
result = parser.parse(raw_packet)

# 检查结果
if result.is_valid:
    print(f"设备ID: {result.device_id}")
    print(f"协议版本: {result.version.name}")
    print(f"命令类型: {result.command_type}")

    # 获取参数值
    for code, param in result.parameters.items():
        print(f"{code}: {param.rtd} (Flag: {param.flag})")
else:
    print(f"解析失败: {result.errors}")
```

### 配置选项

```python
from app.protocols.models import ParserConfig

# 自定义配置
config = ParserConfig(
    strict_mode=False,        # 非严格模式，允许部分错误
    validate_crc=True,        # 启用 CRC 校验
    auto_decrypt=True,        # 自动解密（需要配置密钥）
    sm4_key=None,            # SM4 密钥（32位十六进制字符）
    max_packet_size=10240,   # 最大包大小
)

parser = HJ212Parser(config)
```

### 生成响应

```python
# 解析接收到的数据
result = parser.parse(raw_packet)

# 生成 ACK 响应
if result.segment.needs_ack:
    response = parser.format_response(result, response_code="9014")
    # 发送 response 给设备
```

## 版本检测逻辑

解析器通过 Flag 字段的位运算自动检测协议版本：

```python
version_bits = (flag >> 2) & 0x3F

if version_bits == 1:
    # HJ 212-2017 版本
elif version_bits >= 2:
    # HJ 212-2025 版本
```

Flag 字段位定义：
- Bit 0: 应答标志（0=不应答, 1=应答）
- Bit 1: 分包标志（0=无分包, 1=有分包）
- Bit 2-7: 版本号（6位）

## 支持的参数编码

### 水质参数（w系列）
- w01001: pH值
- w01018: 化学需氧量 (COD)
- w21003: 氨氮
- w21011: 总磷
- w21001: 总氮

### 空气质量参数（a系列）
- a01011: 烟气流速
- a01012: 烟气温度
- a34013: 烟尘(颗粒物)
- a21026: 二氧化硫 (SO2)
- a21002: 氮氧化物 (NOx)

### 电力参数（d系列，2025版本）
- d10001: 总有功功率
- d10007: A相电流
- d10010: 功率因数

### 生产工况参数（p系列，2025版本）
- p10001: 风机电流
- p10003: 风机转速

## 测试

运行测试：

```bash
cd backend
python test_parser_simple.py
```

测试覆盖：
- HJ 212-2017 版本解析
- HJ 212-2025 版本解析
- 版本自动检测
- CRC 校验
- 分包处理
- 响应生成
- 多种数据类型（水质、空气、电力）

## SM4 加密支持（2025版本）

解析器预留了 SM4 加密/解密接口：

```python
def _decrypt_sm4(self, encrypted_content: str, key: str) -> str:
    """
    解密 SM4 加密的内容

    需要实现：
    1. 安装 gmssl 或其他支持 SM4 的库
    2. 实现 SM4-ECB 解密算法
    3. 返回解密后的明文
    """
    # TODO: 实现 SM4 解密
    pass
```

当检测到 2025 版本且 CP 内容为十六进制编码时，解析器会自动识别为加密内容并尝试解密。

## 注意事项

1. **编码**：所有文本数据使用 ASCII 编码
2. **CRC校验**：使用 ANSI CRC16（多项式 0xA001）
3. **时间戳**：QN 字段精确到毫秒（YYYYMMDDHHMMSSmmm）
4. **设备ID**：MN 字段固定 24 个字符
5. **分包**：支持大数据分包传输（通过 PNUM/PNO 字段）

## 扩展开发

### 添加新参数

在 `enums.py` 中添加：

```python
class ParameterCode(str, Enum):
    # 添加新参数
    NEW_PARAM = "x12345"  # 新参数编码

# 更新描述和单位映射
PARAMETER_DESCRIPTIONS["x12345"] = "新参数描述"
PARAMETER_UNITS["x12345"] = "单位"
```

### 自定义验证

继承 `ParserConfig` 添加自定义配置：

```python
class CustomConfig(ParserConfig):
    custom_validation: bool = True

    def validate_custom(self, data):
        # 自定义验证逻辑
        pass
```

## 许可

本项目遵循 EcoMind-AI 项目许可。