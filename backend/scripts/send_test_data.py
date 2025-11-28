#!/usr/bin/env python3
"""
Send test monitoring data via TCP Gateway.

This script sends HJ212 protocol packets to the TCP Gateway to simulate
device data uploads. The data will be stored and can be queried via API.

Usage:
    python scripts/send_test_data.py --value 500 --pollutant w01018
    python scripts/send_test_data.py --value 500 --pollutant w01018 --device TEST001
"""

import socket
import argparse
import sys
from datetime import datetime


def calculate_crc16(data: bytes) -> int:
    """
    Calculate CRC16 checksum for the given data.
    Using ANSI CRC16 polynomial: 0xA001
    """
    crc = 0xFFFF  # Initial value

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001  # Polynomial
            else:
                crc = crc >> 1

    return crc


def calculate_crc(data: str) -> str:
    """Calculate CRC16 for HJ212 protocol and return as hex string."""
    crc = calculate_crc16(data.encode('ascii'))
    return f"{crc:04X}"


def create_hj212_packet(
    device_id: str,
    pollutant_code: str,
    value: float,
    timestamp: datetime = None
) -> bytes:
    """
    Create a valid HJ212-2017 protocol packet.

    Args:
        device_id: Device identifier (MN)
        pollutant_code: Pollutant code (e.g., w01018 for COD)
        value: Measurement value
        timestamp: Data timestamp (default: now)

    Returns:
        Complete HJ212 packet as bytes
    """
    if timestamp is None:
        timestamp = datetime.now()

    data_time = timestamp.strftime("%Y%m%d%H%M%S")
    qn = data_time + "000"

    # Build CP (data content)
    # Format: DataTime=YYYYMMDDHHMMSS;pollutant-Rtd=value,pollutant-Flag=N
    cp = f"DataTime={data_time};{pollutant_code}-Rtd={value},{pollutant_code}-Flag=N"

    # Build data segment
    # QN: Query Number (timestamp)
    # ST: System Type (32 = water pollution source)
    # CN: Command Number (2011 = realtime data upload)
    # PW: Password
    # MN: Device ID
    # Flag: Response flag (4 = don't need response, 0 = need response)
    # CP: Data content
    data_segment = (
        f"QN={qn};"
        f"ST=32;"
        f"CN=2011;"
        f"PW=123456;"
        f"MN={device_id};"
        f"Flag=4;"
        f"CP=&&{cp}&&"
    )

    # Calculate CRC
    crc_hex = calculate_crc(data_segment)

    # Build complete packet
    # Format: ##LLLL + data_segment + CRC + \r\n
    # LLLL: 4-digit length of data_segment
    data_len = len(data_segment)
    packet = f"##{data_len:04d}{data_segment}{crc_hex}\r\n"

    return packet.encode()


def send_packet(host: str, port: int, packet: bytes, timeout: float = 5.0) -> bool:
    """
    Send packet to TCP Gateway.

    Args:
        host: Gateway host
        port: Gateway port
        packet: HJ212 packet bytes
        timeout: Connection timeout

    Returns:
        True if sent successfully
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(packet)

            # Try to receive ACK
            try:
                response = sock.recv(1024)
                if response:
                    print(f"Received ACK: {response.decode('utf-8', errors='ignore')}")
            except socket.timeout:
                print("No ACK received (this is normal for Flag=4 packets)")

            return True

    except ConnectionRefusedError:
        print(f"Error: Cannot connect to {host}:{port}")
        print("Make sure the TCP Gateway is running.")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Send test monitoring data to TCP Gateway"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="TCP Gateway host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9880,
        help="TCP Gateway port (default: 9880)"
    )
    parser.add_argument(
        "--device",
        default="TESTDEV001",
        help="Device ID (default: TESTDEV001)"
    )
    parser.add_argument(
        "--pollutant",
        default="w01018",
        help="Pollutant code (default: w01018 for COD)"
    )
    parser.add_argument(
        "--value",
        type=float,
        required=True,
        help="Measurement value"
    )

    args = parser.parse_args()

    print("=" * 50)
    print("EcoMind-AI Test Data Sender")
    print("=" * 50)
    print(f"Target: {args.host}:{args.port}")
    print(f"Device: {args.device}")
    print(f"Pollutant: {args.pollutant}")
    print(f"Value: {args.value}")
    print("=" * 50)

    # Create packet
    packet = create_hj212_packet(
        device_id=args.device,
        pollutant_code=args.pollutant,
        value=args.value
    )

    print(f"\nPacket ({len(packet)} bytes):")
    print(packet.decode())

    # Send packet
    print("\nSending...")
    success = send_packet(args.host, args.port, packet)

    if success:
        print("\n✓ Packet sent successfully!")
        print("\nTo verify:")
        print("1. Check the dashboard at http://localhost:3000")
        print("2. Or query the API:")
        print(f"   curl http://localhost:8000/api/v1/data?device_id={args.device}")
    else:
        print("\n✗ Failed to send packet")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
