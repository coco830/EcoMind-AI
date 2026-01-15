"""
TCP Gateway Server for HJ212 Protocol

This module implements an async TCP server that receives HJ212 protocol data,
parses it, stores to TDengine, and sends ACK responses.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Set
from datetime import datetime

from sqlalchemy import select

from app.protocols.parser import HJ212Parser
from app.protocols.models import ParserConfig, ParsedData
from app.db.tdengine_client import get_tdengine_client
from app.db.postgres import AsyncSessionLocal
from app.models.device import Device
from app.services.alarm_service import check_thresholds_and_create_alarms

logger = logging.getLogger(__name__)


class TCPGatewayServer:
    """
    Async TCP server for HJ212 protocol data collection

    Features:
    - Receives HJ212 protocol messages via TCP
    - Parses and validates messages
    - Stores data to TDengine
    - Sends ACK responses
    - Handles multiple concurrent connections
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 9880,
                 max_connections: int = 100):
        """
        Initialize TCP Gateway Server

        Args:
            host: Host to bind to
            port: Port to listen on
            max_connections: Maximum concurrent connections
        """
        self.host = host
        self.port = port
        self.max_connections = max_connections

        # Parser configuration
        self.parser_config = ParserConfig(
            strict_mode=False,
            validate_crc=True,
            auto_decrypt=False  # SM4 decryption not yet implemented
        )
        self.parser = HJ212Parser(self.parser_config)

        # TDengine client
        self.tdengine_client = get_tdengine_client()

        # Server state
        self.server: Optional[asyncio.Server] = None
        self.active_connections: Set[asyncio.Task] = set()
        self.running = False

        # Statistics
        self.stats = {
            'messages_received': 0,
            'messages_parsed': 0,
            'messages_stored': 0,
            'messages_failed': 0,
            'connections_total': 0,
            'connections_active': 0
        }

    async def start(self):
        """Start the TCP server"""
        try:
            # Initialize TDengine
            await self.tdengine_client.connect()
            await self.tdengine_client.init_database()

            # Start TCP server
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )

            self.running = True

            addr = self.server.sockets[0].getsockname()
            logger.info(f"TCP Gateway Server started on {addr[0]}:{addr[1]}")

            async with self.server:
                await self.server.serve_forever()

        except Exception as e:
            logger.error(f"Failed to start TCP server: {e}")
            raise

    async def stop(self):
        """Stop the TCP server gracefully"""
        self.running = False

        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        # Cancel active connections
        for task in self.active_connections:
            task.cancel()

        # Wait for all connections to close
        if self.active_connections:
            await asyncio.gather(*self.active_connections, return_exceptions=True)

        # Close TDengine connection
        await self.tdengine_client.close()

        logger.info("TCP Gateway Server stopped")

    async def handle_client(self, reader: asyncio.StreamReader,
                           writer: asyncio.StreamWriter):
        """
        Handle individual client connection

        Args:
            reader: Stream reader for incoming data
            writer: Stream writer for responses
        """
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")

        self.stats['connections_total'] += 1
        self.stats['connections_active'] += 1

        # Create task for this connection
        task = asyncio.current_task()
        self.active_connections.add(task)

        try:
            # Read data with timeout
            while self.running:
                try:
                    # Read until we get a complete packet
                    # HJ212 packets end with \r\n
                    data = await asyncio.wait_for(
                        reader.readuntil(b'\r\n'),
                        timeout=60.0  # 60 second timeout
                    )

                    if not data:
                        break

                    # Process the message
                    await self.process_message(data, writer, addr)

                except asyncio.TimeoutError:
                    logger.debug(f"Connection timeout from {addr}")
                    break
                except asyncio.IncompleteReadError:
                    logger.debug(f"Incomplete read from {addr}")
                    break

        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")

        finally:
            # Clean up
            self.stats['connections_active'] -= 1
            self.active_connections.discard(task)

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

            logger.info(f"Connection closed from {addr}")

    async def process_message(self, raw_data: bytes,
                             writer: asyncio.StreamWriter,
                             addr: tuple):
        """
        Process incoming HJ212 message

        Args:
            raw_data: Raw message bytes
            writer: Stream writer for response
            addr: Client address
        """
        self.stats['messages_received'] += 1

        try:
            # Parse the message
            parsed_data = self.parser.parse(raw_data)

            if parsed_data.is_valid:
                self.stats['messages_parsed'] += 1
                logger.info(f"Parsed message from {addr}: "
                          f"MN={parsed_data.device_id}, "
                          f"CN={parsed_data.segment.cn}, "
                          f"Version={parsed_data.version.name}")

                # Store to TDengine
                success = await self.store_data(parsed_data)
                if success:
                    self.stats['messages_stored'] += 1

                # Send ACK if required
                if parsed_data.segment.needs_ack:
                    await self.send_ack(writer, parsed_data)

            else:
                self.stats['messages_failed'] += 1
                logger.warning(f"Invalid message from {addr}: {parsed_data.errors}")

        except Exception as e:
            self.stats['messages_failed'] += 1
            logger.error(f"Failed to process message from {addr}: {e}")

    async def store_data(self, parsed_data: ParsedData) -> bool:
        """
        Store parsed data to TDengine and check thresholds

        Args:
            parsed_data: Parsed HJ212 data

        Returns:
            True if successful
        """
        try:
            # Extract device info
            device_id = parsed_data.device_id
            timestamp = parsed_data.segment.timestamp
            system_code = parsed_data.segment.st
            command_code = parsed_data.segment.cn
            org_id = device_id[:8]  # First 8 chars as org ID

            # Lookup device from PostgreSQL for threshold configuration
            device = await self._get_device_by_mn(device_id)

            # Store each parameter
            stored_count = 0
            alarm_count = 0
            for param_code, param_value in parsed_data.parameters.items():
                if param_code == "DataTime":
                    continue

                # Skip if no real-time value
                if param_value.rtd is None:
                    continue

                # Store to TDengine
                success = await self.tdengine_client.insert_monitoring_data(
                    device_id=device_id,
                    pollutant_code=param_code,
                    org_id=org_id,
                    timestamp=timestamp,
                    value=param_value.rtd,
                    flag=param_value.flag or "N",
                    status=0 if param_value.flag == "N" else 1
                )

                if success:
                    stored_count += 1

                    # Check thresholds and create alarms if device config exists
                    if device is not None:
                        try:
                            alarms = await check_thresholds_and_create_alarms(
                                device=device,
                                pollutant_code=param_code,
                                value=param_value.rtd,
                                flag=param_value.flag or "N",
                            )
                            alarm_count += len(alarms)
                        except Exception as e:
                            logger.warning(f"Failed to check thresholds: {e}")

            logger.info(
                f"Stored {stored_count} parameters for device {device_id}, "
                f"created {alarm_count} alarms"
            )
            return stored_count > 0

        except Exception as e:
            logger.error(f"Failed to store data to TDengine: {e}")
            return False

    async def _get_device_by_mn(self, mn: str) -> Optional[Device]:
        """
        Get device by MN from PostgreSQL

        Args:
            mn: Device MN identifier

        Returns:
            Device or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Device).where(Device.mn == mn)
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"Failed to lookup device {mn}: {e}")
            return None

    async def send_ack(self, writer: asyncio.StreamWriter,
                       parsed_data: ParsedData):
        """
        Send ACK response to client

        Args:
            writer: Stream writer
            parsed_data: Original parsed data
        """
        try:
            # Format ACK response
            response = self.parser.format_response(parsed_data, response_code="9014")

            # Send response
            writer.write(response)
            await writer.drain()

            logger.debug(f"Sent ACK for device {parsed_data.device_id}")

        except Exception as e:
            logger.error(f"Failed to send ACK: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return self.stats.copy()


# Singleton server instance
_server_instance: Optional[TCPGatewayServer] = None


def get_tcp_server(host: str = "0.0.0.0", port: int = 9880) -> TCPGatewayServer:
    """Get singleton TCP server instance"""
    global _server_instance

    if _server_instance is None:
        _server_instance = TCPGatewayServer(host=host, port=port)

    return _server_instance


async def run_tcp_server(host: str = "0.0.0.0", port: int = 9880):
    """Run TCP server as standalone"""
    server = get_tcp_server(host, port)

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Shutting down TCP server...")
        await server.stop()


if __name__ == "__main__":
    # Run standalone for testing
    import sys
    import structlog

    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Run server
    asyncio.run(run_tcp_server())