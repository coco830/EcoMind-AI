"""HTTP Gateway API for receiving forwarded HJ212 data.

此接口用于接收从 TCP 代理转发过来的 HJ212 协议数据。
由于云托管只支持 HTTP，设备的 TCP 连接通过服务器上的转发脚本
转换为 HTTP 请求发送到此接口。

Security:
- 使用 API Key 验证转发请求的合法性
- 设备认证仍通过 MN 号进行
"""

from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Header, status
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.pollutant_library import get_pollutant_name, is_known_pollutant
from app.gateway.hj212_parser import HJ212Parser
from app.gateway.device_registry import get_device_registry
from app.services.monitoring_service import MonitoringService
from app.db.postgres import AsyncSessionLocal

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()


class HJ212DataRequest(BaseModel):
    """接收 HJ212 数据的请求体"""
    raw_data: str = Field(..., description="原始 HJ212 数据包")
    source_ip: Optional[str] = Field(None, description="设备源 IP 地址")
    received_at: Optional[datetime] = Field(None, description="接收时间")


class HJ212DataResponse(BaseModel):
    """HJ212 数据处理响应"""
    success: bool
    message: str
    device_mn: Optional[str] = None
    pollutant_count: Optional[int] = None
    response_packet: Optional[str] = None


@router.post("/hj212", response_model=HJ212DataResponse)
async def receive_hj212_data(
    request: HJ212DataRequest,
    x_gateway_key: str = Header(..., description="Gateway API Key for authentication"),
) -> HJ212DataResponse:
    """接收从 TCP 代理转发的 HJ212 数据。

    此接口用于云托管环境，设备通过服务器上的 TCP 转发脚本
    将 HJ212 数据转换为 HTTP 请求发送到此接口。

    Headers:
        X-Gateway-Key: Gateway API Key (在环境变量中配置)

    Returns:
        处理结果及 HJ212 响应数据包（用于回传给设备）
    """
    # 验证 Gateway API Key
    expected_key = getattr(settings, 'gateway_api_key', None)
    if not expected_key:
        # 如果未配置 key，使用默认值（生产环境应该配置）
        expected_key = "ecomind-gateway-key-2024"

    if x_gateway_key != expected_key:
        logger.warning(
            "Invalid gateway API key",
            source_ip=request.source_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid gateway API key",
        )

    # 解析 HJ212 数据包
    parser = HJ212Parser()
    packet = parser.parse(request.raw_data)

    if packet is None:
        logger.warning(
            "Failed to parse HJ212 packet",
            source_ip=request.source_ip,
            data_preview=request.raw_data[:100] if request.raw_data else "",
        )
        return HJ212DataResponse(
            success=False,
            message="Invalid HJ212 packet format",
        )

    # 设备认证 - 通过 MN 号查询数据库
    device_registry = get_device_registry()
    device_info = await device_registry.get_device_by_mn(packet.mn)

    if device_info is None:
        logger.warning(
            "Device authentication failed - unregistered device",
            mn=packet.mn,
            source_ip=request.source_ip,
        )
        # 返回错误响应包
        error_response = parser.build_response(packet, result_code=0, result_info="Unregistered device")
        return HJ212DataResponse(
            success=False,
            message="Unregistered device",
            device_mn=packet.mn,
            response_packet=error_response.decode("utf-8"),
        )

    org_id = str(device_info.org_id)

    # 处理监测数据
    if packet.is_realtime or packet.is_minute_data or packet.is_hour_data:
        result = await _handle_monitoring_data(packet, device_info, org_id, request.source_ip)

        # 构建成功响应包
        success_response = parser.build_response(packet, result_code=1)

        return HJ212DataResponse(
            success=True,
            message="Data processed successfully",
            device_mn=packet.mn,
            pollutant_count=result.get("pollutant_count", 0),
            response_packet=success_response.decode("utf-8"),
        )

    elif packet.is_heartbeat:
        logger.debug("Heartbeat received via HTTP", mn=packet.mn)
        # 更新设备心跳时间和状态
        await _update_device_heartbeat(packet.mn)
        success_response = parser.build_response(packet, result_code=1)
        return HJ212DataResponse(
            success=True,
            message="Heartbeat acknowledged",
            device_mn=packet.mn,
            response_packet=success_response.decode("utf-8"),
        )

    elif packet.is_login:
        # CN=9021 设备登录请求，返回 CN=9022 登录响应
        logger.info("Device login request via HTTP", mn=packet.mn, org_id=org_id)
        # 更新设备心跳时间和状态
        await _update_device_heartbeat(packet.mn)
        # 返回登录成功响应 (QnRtn=1 表示成功)
        login_response = parser.build_response(packet, result_code=1)
        return HJ212DataResponse(
            success=True,
            message="Login successful",
            device_mn=packet.mn,
            response_packet=login_response.decode("utf-8"),
        )

    else:
        logger.debug("Unknown command via HTTP", cn=packet.cn, mn=packet.mn)
        success_response = parser.build_response(packet, result_code=1)
        return HJ212DataResponse(
            success=True,
            message=f"Command {packet.cn} acknowledged",
            device_mn=packet.mn,
            response_packet=success_response.decode("utf-8"),
        )


async def _handle_monitoring_data(
    packet: Any,
    device_info: Any,
    org_id: str,
    source_ip: Optional[str],
) -> dict[str, Any]:
    """处理监测数据并存储到 MySQL。

    Args:
        packet: 解析后的 HJ212 数据包
        device_info: 设备信息
        org_id: 组织 ID
        source_ip: 来源 IP

    Returns:
        处理结果字典
    """
    if not packet.cp or "pollutants" not in packet.cp:
        return {"pollutant_count": 0}

    data_time = packet.cp.get("DataTime", datetime.utcnow())
    pollutants: dict[str, dict[str, Any]] = packet.cp["pollutants"]

    # 确定数据类型
    if packet.is_realtime:
        data_type = "realtime"
    elif packet.is_minute_data:
        data_type = "minute"
    elif packet.is_hour_data:
        data_type = "hour"
    else:
        data_type = "unknown"

    # ============================================================
    # 存储到 MySQL (业务数据库)
    # ============================================================
    mysql_saved = 0
    async with AsyncSessionLocal() as db:
        service = MonitoringService(db)

        for pol_code, pol_data in pollutants.items():
            # 获取监测值
            value = pol_data.get("Rtd") or pol_data.get("Avg")
            if value is None:
                continue

            flag = pol_data.get("Flag", "N")
            pollutant_name = get_pollutant_name(pol_code) if is_known_pollutant(pol_code) else None

            try:
                await service.insert_monitoring_data(
                    device_id=packet.mn,
                    device_name=device_info.name,
                    org_id=org_id,
                    pollutant_code=pol_code,
                    pollutant_name=pollutant_name,
                    ts=data_time,
                    value=float(value),
                    flag=str(flag),
                    status=0,
                    data_type=data_type,
                )
                mysql_saved += 1
            except Exception as e:
                logger.error(
                    "Failed to insert to MySQL",
                    mn=packet.mn,
                    pollutant=pol_code,
                    error=str(e),
                )

    logger.info(
        "Monitoring data processed via HTTP",
        mn=packet.mn,
        org_id=org_id,
        data_type=data_type,
        pollutant_count=len(pollutants),
        mysql_saved=mysql_saved,
        source_ip=source_ip,
    )

    return {
        "pollutant_count": len(pollutants),
        "mysql_saved": mysql_saved,
    }


async def _update_device_heartbeat(mn: str) -> None:
    """更新设备心跳时间和在线状态。

    Args:
        mn: 设备 MN 号
    """
    from sqlalchemy import select
    from app.models.device import Device
    from app.services.alarm_service import AlarmService

    try:
        async with AsyncSessionLocal() as db:
            now = datetime.utcnow()
            result = await db.execute(select(Device).where(Device.mn == mn))
            device = result.scalar_one_or_none()
            if not device:
                return

            was_offline = device.status == "offline"
            device.last_heartbeat = now
            device.status = "online"

            # If device recovered, resolve any offline alarms
            if was_offline:
                alarm_service = AlarmService(db)
                await alarm_service.resolve_device_offline_alarms(device.id, resolved_at=now)

            await db.commit()
            logger.info("Device heartbeat updated", mn=mn)
    except Exception as e:
        logger.error("Failed to update device heartbeat", mn=mn, error=str(e))


@router.get("/health")
async def gateway_health():
    """Gateway 健康检查接口"""
    return {
        "status": "healthy",
        "service": "hj212-gateway",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/debug/db-config")
async def debug_db_config():
    """Debug: 查看数据库配置（仅用于排查问题）"""
    from app.core.config import get_settings
    from app.db.postgres import db_url, is_mysql, is_sqlite
    s = get_settings()
    return {
        "mysql_host": s.mysql_host,
        "mysql_port": s.mysql_port,
        "mysql_db": s.mysql_db,
        "mysql_user": s.mysql_user,
        "mysql_password_set": bool(s.mysql_password),
        "mysql_password_len": len(s.mysql_password) if s.mysql_password else 0,
        "database_url_prefix": s.database_url[:30] if s.database_url else None,
        "actual_db_url_prefix": db_url[:50] if db_url else None,
        "is_mysql": is_mysql,
        "is_sqlite": is_sqlite,
    }


@router.get("/debug/test-user-query")
async def debug_test_user_query():
    """Debug: 测试用户查询"""
    from sqlalchemy import select, text
    from app.db.postgres import AsyncSessionLocal
    from app.models.user import User

    try:
        async with AsyncSessionLocal() as session:
            # Raw query first
            result = await session.execute(text("SELECT id, username, role FROM users WHERE username = 'huanbao'"))
            row = result.fetchone()
            if row:
                return {
                    "success": True,
                    "raw_query": {"id": str(row[0]), "username": row[1], "role": row[2]}
                }
            return {"success": False, "message": "User not found in raw query"}
    except Exception as e:
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@router.post("/debug/test-login")
async def debug_test_login(username: str = "huanbao", password: str = "huanbao@123"):
    """Debug: 测试完整登录流程"""
    from sqlalchemy import select
    from app.db.postgres import AsyncSessionLocal
    from app.models.user import User
    from app.core.security import verify_password, create_access_token

    steps = []
    try:
        steps.append("1. Starting login test")

        async with AsyncSessionLocal() as session:
            steps.append("2. Session created")

            # Query user
            result = await session.execute(
                select(User).where(User.username == username)
            )
            steps.append("3. Query executed")

            user = result.scalar_one_or_none()
            steps.append(f"4. User found: {user is not None}")

            if user is None:
                return {"success": False, "steps": steps, "error": "User not found"}

            steps.append(f"5. User data: id={user.id}, username={user.username}, is_active={user.is_active}")

            # Verify password
            pwd_valid = verify_password(password, user.hashed_password)
            steps.append(f"6. Password valid: {pwd_valid}")

            if not pwd_valid:
                return {"success": False, "steps": steps, "error": "Invalid password"}

            # Check active
            if not user.is_active:
                return {"success": False, "steps": steps, "error": "User inactive"}

            steps.append("7. Creating token")
            token = create_access_token(data={"sub": str(user.id)})
            steps.append("8. Token created successfully")

            return {
                "success": True,
                "steps": steps,
                "token_preview": token[:50] + "..."
            }

    except Exception as e:
        import traceback
        return {
            "success": False,
            "steps": steps,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc()
        }
