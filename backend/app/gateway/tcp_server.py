"""TCP Gateway Server for HJ 212 Protocol Data Collection.

支持宽表模式：将同一时间点的所有污染物一次性写入数据库。
符合 HJ 212-2017/2025 标准。

Security:
- Device authentication via MN number lookup
- Multi-tenant data isolation via org_id
- Unregistered devices are rejected
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.encryption import get_sm4_cipher
from app.core.pollutant_library import is_known_pollutant, get_pollutant_name
from app.db.tdengine import get_tdengine_client
from app.gateway.hj212_parser import HJ212Parser, HJ212Packet
from app.gateway.device_registry import get_device_registry, DeviceInfo

settings = get_settings()
logger = structlog.get_logger()


class DeviceConnection:
    """Represents a connected device with authentication info."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        mn: str | None = None,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.mn = mn
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        self.addr = writer.get_extra_info("peername")
        # Device authentication info (populated after MN lookup)
        self.device_info: Optional[DeviceInfo] = None
        self.authenticated: bool = False

    def update_heartbeat(self) -> None:
        """Update last heartbeat time."""
        self.last_heartbeat = datetime.utcnow()

    @property
    def org_id(self) -> Optional[UUID]:
        """Get the organization ID from authenticated device info."""
        return self.device_info.org_id if self.device_info else None

    @property
    def device_id(self) -> Optional[UUID]:
        """Get the device ID from authenticated device info."""
        return self.device_info.device_id if self.device_info else None


class TCPGateway:
    """TCP Gateway for HJ 212 protocol data collection.

    Security features:
    - Device authentication via MN number lookup in database
    - Multi-tenant isolation via org_id
    - Unregistered devices are rejected
    """

    def __init__(self) -> None:
        self.host = settings.host
        self.port = settings.tcp_gateway_port
        self.parser = HJ212Parser()
        self.connections: dict[str, DeviceConnection] = {}
        self.server: asyncio.Server | None = None
        self._running = False
        self._sm4_cipher = None
        self._device_registry = get_device_registry()

    async def start(self) -> None:
        """Start TCP gateway server."""
        self._running = True
        self.server = await asyncio.start_server(
            self._handle_connection,
            self.host,
            self.port,
        )
        logger.info("TCP Gateway listening", host=self.host, port=self.port)

        async with self.server:
            await self.server.serve_forever()

    def stop(self) -> None:
        """Stop TCP gateway server."""
        self._running = False
        if self.server:
            self.server.close()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle incoming device connection."""
        addr = writer.get_extra_info("peername")
        logger.info("Device connected", addr=addr)

        connection = DeviceConnection(reader, writer)

        try:
            while self._running:
                data = await asyncio.wait_for(
                    reader.read(4096),
                    timeout=300.0,  # 5 minute timeout
                )

                if not data:
                    break

                await self._process_data(connection, data)

        except asyncio.TimeoutError:
            logger.warning("Connection timeout", addr=addr, mn=connection.mn)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Connection error", addr=addr, error=str(e))
        finally:
            # Cleanup
            if connection.mn and connection.mn in self.connections:
                del self.connections[connection.mn]

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

            logger.info("Device disconnected", addr=addr, mn=connection.mn)

    async def _process_data(
        self,
        connection: DeviceConnection,
        data: bytes,
    ) -> None:
        """Process incoming data from device.

        Security: Authenticates device via MN number lookup and enforces
        multi-tenant isolation by associating data with the correct org_id.
        """
        # Try to decrypt if encrypted (check for SM4 marker or config)
        decrypted_data = self._try_decrypt(data)

        # Parse HJ 212 packet
        packet = self.parser.parse(decrypted_data)

        if packet is None:
            logger.warning(
                "Failed to parse packet",
                addr=connection.addr,
                data_preview=data[:100],
            )
            return

        # Authenticate device if MN is provided and not yet authenticated
        if packet.mn and not connection.authenticated:
            await self._authenticate_device(connection, packet.mn)

        # Reject data from unauthenticated devices
        if not connection.authenticated:
            logger.warning(
                "Rejecting data from unauthenticated device",
                addr=connection.addr,
                mn=packet.mn,
            )
            # Still send response to maintain protocol compliance
            response = self.parser.build_response(packet, error=True)
            connection.writer.write(response)
            await connection.writer.drain()
            return

        connection.update_heartbeat()

        # Process based on command type
        if packet.is_realtime or packet.is_minute_data or packet.is_hour_data:
            await self._handle_monitoring_data(connection, packet)
        elif packet.is_heartbeat:
            await self._handle_heartbeat(connection, packet)
        else:
            logger.debug("Unknown command", cn=packet.cn, mn=packet.mn)

        # Send acknowledgment
        response = self.parser.build_response(packet)
        connection.writer.write(response)
        await connection.writer.drain()

    async def _authenticate_device(
        self,
        connection: DeviceConnection,
        mn: str,
    ) -> bool:
        """Authenticate device by MN number lookup.

        Args:
            connection: Device connection
            mn: Device MN number

        Returns:
            True if device is authenticated, False otherwise
        """
        device_info = await self._device_registry.get_device_by_mn(mn)

        if device_info is None:
            logger.warning(
                "Device authentication failed - unregistered device",
                mn=mn,
                addr=connection.addr,
            )
            connection.authenticated = False
            return False

        # Update connection with device info
        connection.mn = mn
        connection.device_info = device_info
        connection.authenticated = True
        self.connections[mn] = connection

        logger.info(
            "Device authenticated successfully",
            mn=mn,
            device_id=str(device_info.device_id),
            org_id=str(device_info.org_id),
            device_name=device_info.name,
            addr=connection.addr,
        )
        return True

    def _try_decrypt(self, data: bytes) -> bytes:
        """Try to decrypt data using SM4 if encrypted."""
        # Check if data appears to be hex-encoded SM4 ciphertext
        try:
            # Simple heuristic: if all characters are hex and length is multiple of 32
            data_str = data.decode("utf-8", errors="ignore")
            if len(data_str) % 32 == 0 and all(
                c in "0123456789ABCDEFabcdef" for c in data_str.strip()
            ):
                if self._sm4_cipher is None:
                    self._sm4_cipher = get_sm4_cipher()
                decrypted = self._sm4_cipher.decrypt_hex(data_str.strip())
                return decrypted.encode("utf-8")
        except Exception:
            pass

        return data

    async def _handle_monitoring_data(
        self,
        connection: DeviceConnection,
        packet: HJ212Packet,
    ) -> None:
        """Handle monitoring data packet (CN=2011, 2051, 2061).

        使用宽表模式：将同一时间点的所有污染物数据一次性写入数据库。
        同时保持窄表兼容，以便现有查询API继续工作。

        Security: Uses authenticated connection's org_id for multi-tenant isolation.
        """
        if not packet.cp or "pollutants" not in packet.cp:
            return

        # Use org_id from authenticated device (no more hardcoding!)
        org_id = str(connection.org_id) if connection.org_id else None
        if not org_id:
            logger.error(
                "Cannot process data - no org_id available",
                mn=packet.mn,
                addr=connection.addr,
            )
            return

        data_time = packet.cp.get("DataTime", datetime.utcnow())
        pollutants: dict[str, dict[str, Any]] = packet.cp["pollutants"]

        tdengine = get_tdengine_client()

        # 确定数据类型
        if packet.is_realtime:
            data_type = "realtime"
        elif packet.is_minute_data:
            data_type = "minute"
        elif packet.is_hour_data:
            data_type = "hour"
        else:
            data_type = "unknown"

        # 记录接收到的污染物信息
        known_codes = []
        unknown_codes = []
        for code in pollutants.keys():
            if is_known_pollutant(code):
                known_codes.append(code)
            else:
                unknown_codes.append(code)

        if unknown_codes:
            logger.info(
                "Received unknown pollutant codes (will attempt to store)",
                mn=packet.mn,
                org_id=org_id,
                unknown_codes=unknown_codes,
            )

        # 方式1: 宽表模式 - 一次性写入所有污染物 (推荐)
        try:
            success = await tdengine.insert_wide_monitoring_data(
                device_id=packet.mn,
                org_id=org_id,  # Now using authenticated org_id
                timestamp=data_time,
                pollutants=pollutants,
                data_type=data_type,
            )
            if success:
                logger.debug(
                    "Wide table insert successful",
                    mn=packet.mn,
                    org_id=org_id,
                    pollutant_count=len(pollutants),
                )
        except Exception as e:
            logger.error(
                "Wide table insert failed",
                mn=packet.mn,
                org_id=org_id,
                error=str(e),
            )

        # 方式2: 窄表模式 - 兼容旧API (可选，保持向后兼容)
        for pol_code, pol_data in pollutants.items():
            # Get value (prefer Rtd for realtime, Avg for averages)
            value = pol_data.get("Rtd") or pol_data.get("Avg")
            if value is None:
                continue

            flag = pol_data.get("Flag", "N")

            try:
                await tdengine.insert_monitoring_data(
                    device_id=packet.mn,
                    pollutant_code=pol_code,
                    org_id=org_id,  # Now using authenticated org_id
                    ts=data_time,
                    value=float(value),
                    flag=str(flag),
                    status=0,
                )
            except Exception as e:
                logger.error(
                    "Failed to insert monitoring data (narrow table)",
                    mn=packet.mn,
                    org_id=org_id,
                    pollutant=pol_code,
                    error=str(e),
                )

        # 记录处理结果
        pol_names = [get_pollutant_name(c) for c in known_codes[:5]]
        logger.debug(
            "Monitoring data processed",
            mn=packet.mn,
            org_id=org_id,
            cn=packet.cn,
            data_type=data_type,
            pollutant_count=len(pollutants),
            sample_pollutants=pol_names,
        )

    async def _handle_heartbeat(
        self,
        connection: DeviceConnection,
        packet: HJ212Packet,
    ) -> None:
        """Handle heartbeat packet."""
        logger.debug("Heartbeat received", mn=packet.mn)
        # TODO: Update device status in PostgreSQL

    @property
    def connection_count(self) -> int:
        """Get number of active connections."""
        return len(self.connections)

    def get_connection(self, mn: str) -> DeviceConnection | None:
        """Get connection by device MN."""
        return self.connections.get(mn)
