#!/usr/bin/env python3
"""
Mock Device Script for HJ212 Protocol Testing

This script simulates a data collection device (数采仪) that sends
HJ212 protocol messages to the TCP gateway.
"""

import sys
import socket
import asyncio
import random
from datetime import datetime
from typing import Optional
import argparse

# Add parent directory to path
sys.path.insert(0, '/home/candy/project/EcoMind-AI/backend')

from app.protocols.crc import calculate_crc16, crc16_to_hex


class MockDevice:
    """Mock device that sends HJ212 protocol messages"""

    def __init__(self, device_id: str = "888888888888888888888888",
                 host: str = "localhost", port: int = 9880):
        """
        Initialize mock device

        Args:
            device_id: 24-character device ID (MN)
            host: TCP server host
            port: TCP server port
        """
        self.device_id = device_id
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None

    def create_packet(self, data_segment: str) -> bytes:
        """
        Create a valid HJ212 packet

        Args:
            data_segment: The data segment content

        Returns:
            Complete packet as bytes
        """
        data_len = len(data_segment)
        crc = calculate_crc16(data_segment.encode('ascii'))
        crc_hex = crc16_to_hex(crc)
        packet = f"##{data_len:04d}{data_segment}{crc_hex}\r\n"
        return packet.encode('ascii')

    def create_2017_realtime_packet(self) -> bytes:
        """Create HJ 212-2017 real-time data packet"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S000")

        # Generate random values
        ph = round(6.5 + random.random() * 2, 2)
        cod = round(20 + random.random() * 40, 1)
        nh3 = round(0.5 + random.random() * 3, 2)
        tp = round(0.1 + random.random() * 0.9, 2)

        data_segment = (
            f"QN={timestamp};"
            f"ST=31;"  # Pollution source
            f"CN=2011;"  # Real-time data
            f"PW=123456;"
            f"MN={self.device_id};"
            f"Flag=5;"  # Version 1 (2017), needs ACK
            f"CP=&&DataTime={timestamp[:14]};"
            f"w01001-Rtd={ph},w01001-Flag=N;"
            f"w01018-Rtd={cod},w01018-Flag=N;"
            f"w21003-Rtd={nh3},w21003-Flag=N;"
            f"w21011-Rtd={tp},w21011-Flag=N&&"
        )

        return self.create_packet(data_segment)

    def create_2025_power_packet(self) -> bytes:
        """Create HJ 212-2025 power monitoring packet"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S000")

        # Generate random power values
        active_power = round(100 + random.random() * 200, 1)
        voltage_a = round(220 + random.random() * 10, 1)
        current_a = round(5 + random.random() * 20, 2)
        power_factor = round(0.8 + random.random() * 0.2, 3)

        data_segment = (
            f"QN={timestamp};"
            f"ST=44;"  # Facility power (2025)
            f"CN=2051;"  # Minute data
            f"PW=123456;"
            f"MN={self.device_id};"
            f"Flag=9;"  # Version 2 (2025), needs ACK
            f"CP=&&DataTime={timestamp[:14]};"
            f"d10001-Rtd={active_power},d10001-Flag=N;"
            f"d10004-Rtd={voltage_a},d10004-Flag=N;"
            f"d10007-Rtd={current_a},d10007-Flag=N;"
            f"d10010-Rtd={power_factor},d10010-Flag=N&&"
        )

        return self.create_packet(data_segment)

    def create_air_quality_packet(self) -> bytes:
        """Create air quality monitoring packet"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S000")

        # Generate random air quality values
        flow_rate = round(10 + random.random() * 20, 1)
        temperature = round(100 + random.random() * 50, 1)
        pm = round(20 + random.random() * 30, 1)
        so2 = round(50 + random.random() * 100, 1)
        nox = round(80 + random.random() * 120, 1)

        data_segment = (
            f"QN={timestamp};"
            f"ST=22;"  # Air quality
            f"CN=2011;"  # Real-time data
            f"PW=123456;"
            f"MN={self.device_id};"
            f"Flag=5;"  # Version 1 (2017), needs ACK
            f"CP=&&DataTime={timestamp[:14]};"
            f"a01011-Rtd={flow_rate},a01011-Flag=N;"
            f"a01012-Rtd={temperature},a01012-Flag=N;"
            f"a34013-Rtd={pm},a34013-Flag=N;"
            f"a21026-Rtd={so2},a21026-Flag=N;"
            f"a21002-Rtd={nox},a21002-Flag=N&&"
        )

        return self.create_packet(data_segment)

    def create_heartbeat_packet(self) -> bytes:
        """Create heartbeat packet"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S000")

        data_segment = (
            f"QN={timestamp};"
            f"ST=31;"
            f"CN=9013;"  # Heartbeat
            f"MN={self.device_id};"
            f"Flag=4"  # No ACK needed
        )

        return self.create_packet(data_segment)

    async def connect(self):
        """Connect to TCP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False

    async def send_packet(self, packet: bytes):
        """Send packet and wait for response"""
        if not self.socket:
            print("Not connected")
            return

        try:
            # Send packet
            self.socket.sendall(packet)
            print(f"Sent: {packet.decode('ascii', errors='ignore')[:100]}...")

            # Wait for ACK (if expected)
            if b"Flag=5" in packet or b"Flag=9" in packet:
                self.socket.settimeout(5.0)
                try:
                    response = self.socket.recv(4096)
                    print(f"Received ACK: {response.decode('ascii', errors='ignore')[:100]}...")
                except socket.timeout:
                    print("No ACK received (timeout)")

        except Exception as e:
            print(f"Error sending packet: {e}")

    def close(self):
        """Close connection"""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("Connection closed")


async def test_single_packet(device_id: str, packet_type: str,
                            host: str, port: int):
    """Test sending a single packet"""
    device = MockDevice(device_id, host, port)

    if not await device.connect():
        return

    # Create packet based on type
    if packet_type == "2017":
        packet = device.create_2017_realtime_packet()
        print("\n=== Sending HJ 212-2017 Real-time Data ===")
    elif packet_type == "2025":
        packet = device.create_2025_power_packet()
        print("\n=== Sending HJ 212-2025 Power Data ===")
    elif packet_type == "air":
        packet = device.create_air_quality_packet()
        print("\n=== Sending Air Quality Data ===")
    elif packet_type == "heartbeat":
        packet = device.create_heartbeat_packet()
        print("\n=== Sending Heartbeat ===")
    else:
        print(f"Unknown packet type: {packet_type}")
        device.close()
        return

    await device.send_packet(packet)
    device.close()


async def test_continuous(device_id: str, interval: int,
                         host: str, port: int):
    """Test continuous data sending"""
    device = MockDevice(device_id, host, port)

    if not await device.connect():
        return

    packet_types = ["2017", "2025", "air"]
    packet_count = 0

    print(f"\n=== Starting continuous test (interval: {interval}s) ===")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            # Rotate through packet types
            packet_type = packet_types[packet_count % len(packet_types)]

            # Create and send packet
            if packet_type == "2017":
                packet = device.create_2017_realtime_packet()
                print(f"[{packet_count+1}] Sending 2017 water quality data")
            elif packet_type == "2025":
                packet = device.create_2025_power_packet()
                print(f"[{packet_count+1}] Sending 2025 power data")
            else:
                packet = device.create_air_quality_packet()
                print(f"[{packet_count+1}] Sending air quality data")

            await device.send_packet(packet)
            packet_count += 1

            # Send heartbeat every 10 packets
            if packet_count % 10 == 0:
                print(f"[HB] Sending heartbeat")
                heartbeat = device.create_heartbeat_packet()
                await device.send_packet(heartbeat)

            # Wait for interval
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\nTest stopped. Sent {packet_count} packets.")
    finally:
        device.close()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Mock HJ212 device for testing TCP gateway"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="TCP server host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9880,
        help="TCP server port (default: 9880)"
    )
    parser.add_argument(
        "--device-id",
        default="888888888888888888888888",
        help="24-character device ID"
    )
    parser.add_argument(
        "--type",
        choices=["2017", "2025", "air", "heartbeat", "continuous"],
        default="2017",
        help="Packet type to send"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Interval for continuous mode (seconds)"
    )

    args = parser.parse_args()

    # Validate device ID length
    if len(args.device_id) != 24:
        print(f"Error: Device ID must be 24 characters (got {len(args.device_id)})")
        sys.exit(1)

    # Run test
    if args.type == "continuous":
        asyncio.run(test_continuous(
            args.device_id, args.interval, args.host, args.port
        ))
    else:
        asyncio.run(test_single_packet(
            args.device_id, args.type, args.host, args.port
        ))


if __name__ == "__main__":
    main()