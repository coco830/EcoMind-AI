"""
Pydantic Models for HJ212 Protocol Data Structures

This module defines the data models for parsed HJ212 protocol messages.
"""

from datetime import datetime
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field, field_validator
from .enums import ProtocolVersion, CommandCode, SystemCode, DataFlag


class ParameterValue(BaseModel):
    """Single parameter value with metadata"""

    code: str = Field(..., description="Parameter code (e.g., w01001)")
    rtd: Optional[float] = Field(None, description="Real-time data value")
    min: Optional[float] = Field(None, description="Minimum value")
    max: Optional[float] = Field(None, description="Maximum value")
    avg: Optional[float] = Field(None, description="Average value")
    cou: Optional[float] = Field(None, description="Cumulative value")
    flag: Optional[str] = Field(None, description="Data flag (N/A/M/F/C/D/S/T/O)")
    eFlag: Optional[str] = Field(None, description="Extended flag")

    @field_validator('flag')
    def validate_flag(cls, v):
        if v and v not in ['N', 'A', 'M', 'F', 'C', 'D', 'S', 'T', 'O']:
            # Allow but log unknown flags for forward compatibility
            pass
        return v


class DataSegment(BaseModel):
    """Parsed data segment of HJ212 message"""

    qn: str = Field(..., description="Request number (YYYYMMDDHHMMSSmmm)")
    st: str = Field(..., description="System type code")
    cn: str = Field(..., description="Command code")
    pw: Optional[str] = Field(None, description="Password")
    mn: str = Field(..., description="Monitor number (24 chars)")
    flag: int = Field(..., description="Flag bits (0-255)")
    pnum: Optional[int] = Field(None, description="Total packet number")
    pno: Optional[int] = Field(None, description="Current packet number")
    cp: Optional[str] = Field(None, description="Raw CP content")

    @property
    def timestamp(self) -> datetime:
        """Parse QN to datetime"""
        try:
            # QN format: YYYYMMDDHHMMSSmmm
            dt_str = self.qn[:14]  # Take YYYYMMDDHHMMss
            return datetime.strptime(dt_str, "%Y%m%d%H%M%S")
        except (ValueError, IndexError):
            return datetime.now()

    @property
    def needs_ack(self) -> bool:
        """Check if message needs acknowledgment"""
        return bool(self.flag & 0x01)

    @property
    def is_split(self) -> bool:
        """Check if message is split into multiple packets"""
        return bool(self.flag & 0x02)

    @property
    def protocol_version(self) -> int:
        """Extract protocol version from flag"""
        return (self.flag >> 2) & 0x3F  # 6 bits for version


class ParsedData(BaseModel):
    """Complete parsed HJ212 message"""

    # Raw data
    raw: bytes = Field(..., description="Original raw message")

    # Packet structure
    header: str = Field(default="##", description="Packet header")
    data_len: int = Field(..., description="Data segment length")
    crc: str = Field(..., description="CRC16 checksum")
    tail: str = Field(default="\r\n", description="Packet tail")

    # Parsed segments
    segment: DataSegment = Field(..., description="Parsed data segment")

    # Parsed CP data (if any)
    parameters: Dict[str, ParameterValue] = Field(
        default_factory=dict,
        description="Parsed parameter values from CP"
    )

    # System info
    system_time: Optional[datetime] = Field(None, description="System time from DataTime field")

    # Metadata
    version: ProtocolVersion = Field(..., description="Detected protocol version")
    is_encrypted: bool = Field(default=False, description="Whether CP was encrypted")
    is_valid: bool = Field(default=True, description="Whether packet passed all validations")
    errors: List[str] = Field(default_factory=list, description="Validation errors if any")

    @property
    def device_id(self) -> str:
        """Get device ID (MN field)"""
        return self.segment.mn

    @property
    def command_type(self) -> str:
        """Get command type description"""
        try:
            return CommandCode(self.segment.cn).name
        except (ValueError, KeyError):
            return f"UNKNOWN_{self.segment.cn}"

    @property
    def system_type(self) -> str:
        """Get system type description"""
        try:
            return SystemCode(self.segment.st).name
        except (ValueError, KeyError):
            return f"UNKNOWN_{self.segment.st}"

    def get_parameter(self, code: str) -> Optional[ParameterValue]:
        """Get parameter value by code"""
        return self.parameters.get(code)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "device_id": self.device_id,
            "timestamp": self.segment.timestamp.isoformat(),
            "command": self.command_type,
            "system": self.system_type,
            "version": self.version.name,
            "is_encrypted": self.is_encrypted,
            "is_valid": self.is_valid,
            "needs_ack": self.segment.needs_ack,
            "parameters": {
                code: {
                    "value": param.rtd,
                    "flag": param.flag,
                    "min": param.min,
                    "max": param.max,
                    "avg": param.avg
                }
                for code, param in self.parameters.items()
            },
            "errors": self.errors
        }


class ParserConfig(BaseModel):
    """Configuration for HJ212 parser"""

    strict_mode: bool = Field(
        default=False,
        description="Strict validation mode (fail on any error)"
    )

    auto_decrypt: bool = Field(
        default=True,
        description="Automatically decrypt encrypted CP data"
    )

    sm4_key: Optional[str] = Field(
        default=None,
        description="SM4 encryption key for 2025 protocol (32 hex chars)"
    )

    max_packet_size: int = Field(
        default=10240,
        description="Maximum allowed packet size in bytes"
    )

    timeout: int = Field(
        default=30,
        description="Timeout for split packet assembly (seconds)"
    )

    validate_crc: bool = Field(
        default=True,
        description="Validate CRC16 checksum"
    )

    validate_timestamp: bool = Field(
        default=False,
        description="Validate QN timestamp is recent"
    )

    max_timestamp_drift: int = Field(
        default=300,
        description="Maximum allowed timestamp drift in seconds"
    )